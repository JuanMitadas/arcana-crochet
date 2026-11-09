"""Shopping bag stored in the session (works for visitors and logged-in customers)."""

from dataclasses import dataclass
from functools import cached_property

from django.db.models import Prefetch

from apps.catalogo.models import Produto, ProdutoFoto, ProdutoVariacao
from apps.core import precos

from . import frete as modulo_frete
from .models import Cupom

CHAVE = "sacola"
MAX_ENCOMENDA = 10


@dataclass
class ItemSacola:
    variacao: ProdutoVariacao
    quantidade: int

    @property
    def produto(self) -> Produto:
        return self.variacao.produto

    @property
    def preco_unitario_centavos(self) -> int:
        return self.variacao.preco_centavos

    @property
    def total_centavos(self) -> int:
        return self.preco_unitario_centavos * self.quantidade

    @property
    def sob_encomenda(self) -> bool:
        return self.produto.disponibilidade == Produto.Disponibilidade.SOB_ENCOMENDA

    @property
    def maximo(self) -> int:
        return MAX_ENCOMENDA if self.sob_encomenda else self.variacao.disponivel

    @property
    def detalhes(self) -> str:
        return " / ".join(filter(None, [self.variacao.cor, self.variacao.tamanho]))

    @property
    def foto(self):
        fotos = self.produto.fotos.all()
        da_variacao = [f for f in fotos if f.variacao_id == self.variacao.id]
        return (da_variacao or list(fotos) or [None])[0]


class Carrinho:
    def __init__(self, request):
        self.session = request.session
        dados = self.session.get(CHAVE) or {}
        self._itens: dict[str, int] = dict(dados.get("itens", {}))
        self.cupom_codigo: str = dados.get("cupom", "")
        self.cep: str = dados.get("cep", "")
        self.frete_codigo: str = dados.get("frete", "")

    # --- persistence ---------------------------------------------------------

    def salvar(self):
        self.session[CHAVE] = {
            "itens": self._itens,
            "cupom": self.cupom_codigo,
            "cep": self.cep,
            "frete": self.frete_codigo,
        }
        self.session.modified = True
        self.__dict__.pop("itens", None)
        self.__dict__.pop("cupom", None)

    def limpar(self):
        self.session.pop(CHAVE, None)
        self.session.modified = True

    # --- items --------------------------------------------------------------

    @property
    def quantidade_total(self) -> int:
        return sum(self._itens.values())

    def __len__(self):
        return self.quantidade_total

    def adicionar(self, variacao: ProdutoVariacao, quantidade: int = 1) -> int:
        """Add to the current quantity within what's available. Return the final quantity."""
        chave = str(variacao.pk)
        return self.definir(variacao, self._itens.get(chave, 0) + quantidade)

    def definir(self, variacao: ProdutoVariacao, quantidade: int) -> int:
        chave = str(variacao.pk)
        item = ItemSacola(variacao, quantidade)
        quantidade = max(0, min(quantidade, item.maximo))
        if quantidade:
            self._itens[chave] = quantidade
        else:
            self._itens.pop(chave, None)
        self.salvar()
        return quantidade

    def remover(self, variacao_id) -> None:
        self._itens.pop(str(variacao_id), None)
        self.salvar()

    @cached_property
    def itens(self) -> list[ItemSacola]:
        if not self._itens:
            return []
        variacoes = (
            ProdutoVariacao.objects.filter(
                pk__in=self._itens.keys(),
                ativa=True,
                produto__status__in=[Produto.Status.ATIVO, Produto.Status.ESGOTADO],
            )
            .select_related("produto", "produto__categoria")
            .prefetch_related(
                Prefetch("produto__fotos", queryset=ProdutoFoto.objects.order_by("ordem"))
            )
        )
        encontrados = {str(v.pk): v for v in variacoes}
        itens = []
        mudou = False
        for chave, quantidade in list(self._itens.items()):
            variacao = encontrados.get(chave)
            if variacao is None:
                self._itens.pop(chave)
                mudou = True
                continue
            item = ItemSacola(variacao, quantidade)
            if quantidade > item.maximo:
                item.quantidade = item.maximo
                mudou = True
                if item.maximo:
                    self._itens[chave] = item.maximo
                else:
                    self._itens.pop(chave)
                    continue
            itens.append(item)
        if mudou:
            self.ajustado = True
            self.session[CHAVE] = {**(self.session.get(CHAVE) or {}), "itens": self._itens}
            self.session.modified = True
        return itens

    ajustado = False  # True when an item was reduced or removed for lack of stock

    # --- amounts ------------------------------------------------------------

    @property
    def subtotal_centavos(self) -> int:
        return sum(item.total_centavos for item in self.itens)

    @property
    def peso_total_g(self) -> int:
        return sum(item.produto.peso_g * item.quantidade for item in self.itens)

    @property
    def prazo_producao_dias(self) -> int:
        prazos = [
            item.produto.prazo_producao_dias or 0 for item in self.itens if item.sob_encomenda
        ]
        return max(prazos, default=0)

    @cached_property
    def cupom(self) -> Cupom | None:
        if not self.cupom_codigo:
            return None
        return Cupom.objects.filter(codigo=self.cupom_codigo).first()

    @property
    def cupom_erro(self) -> str:
        if not self.cupom_codigo:
            return ""
        if self.cupom is None:
            return "Cupom não encontrado."
        try:
            self.cupom.validar(self.subtotal_centavos)
        except Exception as erro:  # ValidationError
            return erro.messages[0] if hasattr(erro, "messages") else str(erro)
        return ""

    @property
    def cupom_valido(self) -> Cupom | None:
        return self.cupom if self.cupom and not self.cupom_erro else None

    @property
    def desconto_cupom_centavos(self) -> int:
        cupom = self.cupom_valido
        return cupom.desconto_produtos(self.subtotal_centavos) if cupom else 0

    @property
    def produtos_com_desconto_centavos(self) -> int:
        return self.subtotal_centavos - self.desconto_cupom_centavos

    def opcoes_frete(self):
        if not modulo_frete.cep_valido(self.cep) or not self.itens:
            return []
        opcoes = modulo_frete.cotar(
            self.cep, self.peso_total_g, self.subtotal_centavos, self.prazo_producao_dias
        )
        cupom = self.cupom_valido
        if cupom and cupom.tipo == Cupom.Tipo.FRETE_GRATIS:
            opcoes = [
                modulo_frete.OpcaoFrete(o.codigo, o.nome, 0, o.prazo_dias, gratis=True)
                if o.codigo == "pac"
                else o
                for o in opcoes
            ]
        return opcoes

    @property
    def frete(self) -> modulo_frete.OpcaoFrete | None:
        opcoes = self.opcoes_frete()
        escolhida = next((o for o in opcoes if o.codigo == self.frete_codigo), None)
        return escolhida or (opcoes[0] if opcoes else None)

    @property
    def frete_centavos(self) -> int:
        return self.frete.preco_centavos if self.frete else 0

    @property
    def total_centavos(self) -> int:
        return self.produtos_com_desconto_centavos + self.frete_centavos

    def desconto_pix_centavos(self) -> int:
        base = self.produtos_com_desconto_centavos
        return base - precos.preco_pix(base)

    @property
    def total_pix_centavos(self) -> int:
        return self.total_centavos - self.desconto_pix_centavos()

    @property
    def falta_para_frete_gratis_centavos(self) -> int:
        from django.conf import settings

        limite = settings.LOJA["FRETE_GRATIS_A_PARTIR_CENTAVOS"]
        return max(0, limite - self.subtotal_centavos) if limite else 0
