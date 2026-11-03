from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models import Avg, Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse

from apps.core.models import ModeloBase


class Categoria(ModeloBase):
    pai = models.ForeignKey(
        "self",
        verbose_name="categoria pai",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="filhas",
    )
    nome = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    descricao = models.CharField("descrição curta", max_length=160, blank=True)
    imagem = models.ImageField(
        upload_to="categorias/", blank=True, help_text="Foto usada no card da categoria."
    )
    ordem = models.PositiveSmallIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return f"{self.pai} › {self.nome}" if self.pai_id else self.nome


class ProdutoQuerySet(models.QuerySet):
    def visiveis(self):
        """Produtos que aparecem na vitrine."""
        return self.filter(status__in=[Produto.Status.ATIVO, Produto.Status.ESGOTADO])

    def com_metricas(self):
        """Anota preço efetivo, nota média, nº de avaliações e unidades vendidas.

        Usa subconsultas (e não JOIN + agregação) para que os números não se
        multipliquem quando a consulta também filtra por variações."""
        from apps.avaliacoes.models import Avaliacao
        from apps.pedidos.models import Pedido, PedidoItem

        avaliacoes = Avaliacao.objects.filter(
            produto=OuterRef("pk"), status=Avaliacao.Status.PUBLICADA
        ).values("produto")
        vendidos = (
            PedidoItem.objects.filter(
                produto=OuterRef("pk"), pedido__status__in=Pedido.STATUS_PAGOS
            )
            .values("produto")
            .annotate(total=Sum("quantidade"))
            .values("total")
        )
        return self.annotate(
            preco_efetivo=Coalesce("preco_promocional_centavos", "preco_centavos"),
            nota_media=Subquery(avaliacoes.annotate(m=Avg("nota")).values("m")),
            total_avaliacoes=Coalesce(Subquery(avaliacoes.annotate(c=Count("pk")).values("c")), 0),
            unidades_vendidas=Coalesce(Subquery(vendidos), 0),
        )


class Produto(ModeloBase):
    class Disponibilidade(models.TextChoices):
        PRONTA_ENTREGA = "pronta_entrega", "Pronta entrega"
        SOB_ENCOMENDA = "sob_encomenda", "Sob encomenda"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ATIVO = "ativo", "Ativo"
        PAUSADO = "pausado", "Pausado"
        ESGOTADO = "esgotado", "Esgotado"
        ARQUIVADO = "arquivado", "Arquivado"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="produtos")
    nome = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    descricao = models.TextField("descrição", max_length=5000, blank=True)
    preco_centavos = models.BigIntegerField("preço (centavos)")
    preco_promocional_centavos = models.BigIntegerField(
        "preço promocional (centavos)", null=True, blank=True
    )
    custo_centavos = models.BigIntegerField(
        "custo (centavos)",
        default=0,
        help_text="Fio + horas de trabalho. Só a equipe vê.",
    )
    disponibilidade = models.CharField(
        max_length=20, choices=Disponibilidade.choices, default=Disponibilidade.PRONTA_ENTREGA
    )
    prazo_producao_dias = models.PositiveSmallIntegerField(
        "prazo de produção (dias)", null=True, blank=True
    )
    peso_g = models.PositiveIntegerField("peso da embalagem (g)")
    altura_cm = models.PositiveSmallIntegerField("altura (cm)")
    largura_cm = models.PositiveSmallIntegerField("largura (cm)")
    comprimento_cm = models.PositiveSmallIntegerField("comprimento (cm)")
    material = models.CharField(max_length=60, blank=True)
    cuidados = models.TextField(
        "cuidados com a peça",
        blank=True,
        help_text="Ex.: lavar à mão em água fria, secar à sombra, na horizontal.",
    )
    video = models.FileField(
        "vídeo",
        upload_to="produtos/videos/",
        blank=True,
        validators=[FileExtensionValidator(["mp4", "webm"])],
        help_text="Opcional. MP4 ou WebM curto, até ~20 MB.",
    )
    personalizavel = models.BooleanField("aceita personalização", default=False)
    destaque = models.BooleanField(default=False, help_text="Aparece na página inicial.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO)
    publicado_em = models.DateTimeField("publicado em", null=True, blank=True)

    objects = ProdutoQuerySet.as_manager()

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["status", "categoria", "preco_centavos"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(preco_centavos__gt=0), name="produto_preco_positivo"
            ),
            models.CheckConstraint(
                condition=Q(preco_promocional_centavos__isnull=True)
                | Q(
                    preco_promocional_centavos__gt=0,
                    preco_promocional_centavos__lt=models.F("preco_centavos"),
                ),
                name="produto_promocao_menor_que_preco",
            ),
            models.CheckConstraint(
                condition=~Q(disponibilidade="sob_encomenda")
                | Q(prazo_producao_dias__isnull=False, prazo_producao_dias__gt=0),
                name="produto_encomenda_exige_prazo",
            ),
        ]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("catalogo:produto", kwargs={"slug": self.slug})

    @property
    def preco_atual_centavos(self) -> int:
        return self.preco_promocional_centavos or self.preco_centavos

    @property
    def em_promocao(self) -> bool:
        return self.preco_promocional_centavos is not None


class ProdutoVariacao(ModeloBase):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="variacoes")
    sku = models.CharField("SKU", max_length=40, unique=True)
    cor = models.CharField(max_length=40, blank=True)
    tamanho = models.CharField(max_length=20, blank=True)
    cor_hex = models.CharField(
        "cor (hex)",
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use o formato #1a2b3c.")],
        help_text="Cor da bolinha no seletor, ex.: #17597c.",
    )
    preco_ajuste_centavos = models.BigIntegerField("ajuste de preço (centavos)", default=0)
    estoque = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Altere pelo registro de movimentações de estoque.",
    )
    estoque_reservado = models.PositiveIntegerField(default=0, editable=False)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "variação"
        verbose_name_plural = "variações"
        ordering = ["produto", "cor", "tamanho"]
        indexes = [models.Index(fields=["cor", "tamanho"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(estoque_reservado__lte=models.F("estoque")),
                name="variacao_reserva_ate_estoque",
            ),
        ]

    def __str__(self):
        detalhes = " · ".join(filter(None, [self.cor, self.tamanho]))
        return f"{self.produto} ({detalhes})" if detalhes else str(self.produto)

    @property
    def disponivel(self) -> int:
        return self.estoque - self.estoque_reservado

    @property
    def preco_centavos(self) -> int:
        return self.produto.preco_atual_centavos + self.preco_ajuste_centavos


class ProdutoEspecificacao(models.Model):
    """Linha da ficha técnica, ex.: "Altura" = "18 cm"."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="especificacoes")
    nome = models.CharField(max_length=60)
    valor = models.CharField(max_length=200)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "item da ficha técnica"
        verbose_name_plural = "ficha técnica"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.nome}: {self.valor}"


def caminho_foto(instancia, nome_arquivo):
    extensao = nome_arquivo.rsplit(".", 1)[-1].lower()
    return f"produtos/{instancia.produto_id}/{instancia.id}.{extensao}"


class ProdutoFoto(ModeloBase):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="fotos")
    variacao = models.ForeignKey(
        ProdutoVariacao,
        verbose_name="variação",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fotos",
        help_text="Deixe vazio se a foto vale para todas as variações.",
    )
    imagem = models.ImageField(upload_to=caminho_foto, width_field="largura", height_field="altura")
    largura = models.PositiveIntegerField(editable=False, null=True)
    altura = models.PositiveIntegerField(editable=False, null=True)
    texto_alternativo = models.CharField(
        "texto alternativo",
        max_length=150,
        help_text="Descreva a foto para leitores de tela, ex.: 'Urso azul de crochê sentado'.",
    )
    ordem = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "foto"
        verbose_name_plural = "fotos"
        ordering = ["produto", "ordem"]

    def __str__(self):
        return f"Foto {self.ordem} de {self.produto}"


class MovimentacaoEstoque(ModeloBase):
    """Toda mudança de estoque passa por aqui. Use ``registrar_movimentacao``."""

    class Tipo(models.TextChoices):
        ENTRADA_PRODUCAO = "entrada_producao", "Entrada de produção"
        VENDA = "venda", "Venda"
        CANCELAMENTO = "cancelamento", "Cancelamento"
        DEVOLUCAO = "devolucao", "Devolução"
        AJUSTE = "ajuste", "Ajuste manual"

    variacao = models.ForeignKey(
        ProdutoVariacao,
        verbose_name="variação",
        on_delete=models.PROTECT,
        related_name="movimentacoes",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    quantidade = models.IntegerField(help_text="Positiva para entrada, negativa para saída.")
    estoque_resultante = models.PositiveIntegerField(editable=False)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "movimentação de estoque"
        verbose_name_plural = "movimentações de estoque"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantidade=0), name="movimentacao_quantidade_nao_zero"
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.quantidade:+d} · {self.variacao}"
