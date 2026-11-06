import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ModeloBase

ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I (read out by phone)


def gerar_codigo_pedido() -> str:
    return "ARC-" + "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(6))


class Cupom(ModeloBase):
    class Tipo(models.TextChoices):
        PERCENTUAL = "percentual", "Percentual (%)"
        FIXO = "fixo", "Valor fixo"
        FRETE_GRATIS = "frete_gratis", "Frete grátis"

    codigo = models.CharField("código", max_length=30, unique=True)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    valor = models.PositiveIntegerField(
        default=0, help_text="Percentual (ex.: 10) ou valor em centavos (ex.: 1500 = R$ 15,00)."
    )
    minimo_centavos = models.PositiveIntegerField("pedido mínimo (centavos)", default=0)
    valido_ate = models.DateTimeField("válido até", null=True, blank=True)
    limite_usos = models.PositiveIntegerField("limite de usos", null=True, blank=True)
    usos = models.PositiveIntegerField(default=0, editable=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "cupom"
        verbose_name_plural = "cupons"
        constraints = [
            models.CheckConstraint(
                condition=~Q(tipo="percentual") | Q(valor__gt=0, valor__lte=100),
                name="cupom_percentual_valido",
            ),
        ]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def validar(self, subtotal_centavos: int) -> None:
        """Raise ValidationError with a message for the customer if it can't be used."""
        if not self.ativo or (self.valido_ate and self.valido_ate < timezone.now()):
            raise ValidationError("Este cupom expirou.")
        if self.limite_usos is not None and self.usos >= self.limite_usos:
            raise ValidationError("Este cupom já atingiu o limite de usos.")
        if subtotal_centavos < self.minimo_centavos:
            from apps.core.templatetags.dinheiro import brl

            raise ValidationError(
                f"Este cupom vale para compras a partir de {brl(self.minimo_centavos)}."
            )

    def desconto_produtos(self, subtotal_centavos: int) -> int:
        if self.tipo == self.Tipo.PERCENTUAL:
            return round(subtotal_centavos * self.valor / 100)
        if self.tipo == self.Tipo.FIXO:
            return min(self.valor, subtotal_centavos)
        return 0

    @property
    def descricao(self) -> str:
        from apps.core.templatetags.dinheiro import brl

        if self.tipo == self.Tipo.PERCENTUAL:
            return f"{self.valor}% de desconto nos produtos"
        if self.tipo == self.Tipo.FIXO:
            return f"{brl(self.valor)} de desconto"
        return "Frete grátis"


class Pedido(ModeloBase):
    class Status(models.TextChoices):
        AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
        PAGO = "pago", "Pagamento aprovado"
        EM_SEPARACAO = "em_separacao", "Em separação"
        ENVIADO = "enviado", "Enviado"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    class Metodo(models.TextChoices):
        PIX = "pix", "Pix"
        CARTAO = "cartao", "Cartão de crédito"

    # Steps shown on the customer's timeline, in order.
    ETAPAS = [Status.PAGO, Status.EM_SEPARACAO, Status.ENVIADO, Status.ENTREGUE]
    STATUS_PAGOS = [Status.PAGO, Status.EM_SEPARACAO, Status.ENVIADO, Status.ENTREGUE]
    PROXIMO = {
        Status.PAGO: Status.EM_SEPARACAO,
        Status.EM_SEPARACAO: Status.ENVIADO,
        Status.ENVIADO: Status.ENTREGUE,
    }

    codigo = models.CharField(
        "código", max_length=12, unique=True, default=gerar_codigo_pedido, editable=False
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos"
    )
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.AGUARDANDO_PAGAMENTO
    )
    metodo_pagamento = models.CharField("forma de pagamento", max_length=10, choices=Metodo.choices)
    parcelas = models.PositiveSmallIntegerField(default=1)

    subtotal_centavos = models.BigIntegerField("subtotal (centavos)")
    desconto_cupom_centavos = models.BigIntegerField("desconto do cupom (centavos)", default=0)
    desconto_pix_centavos = models.BigIntegerField("desconto do Pix (centavos)", default=0)
    frete_centavos = models.BigIntegerField("frete (centavos)", default=0)
    total_centavos = models.BigIntegerField("total (centavos)")
    cupom = models.ForeignKey(Cupom, on_delete=models.PROTECT, null=True, blank=True)

    endereco_entrega = models.JSONField("endereço de entrega")
    frete_servico = models.CharField("serviço de entrega", max_length=60)
    frete_prazo_dias = models.PositiveSmallIntegerField("prazo de entrega (dias úteis)")
    transportadora = models.CharField(max_length=60, blank=True)
    codigo_rastreio = models.CharField("código de rastreio", max_length=40, blank=True)
    url_rastreio = models.URLField("link de rastreio", blank=True)
    observacao = models.CharField("observação do cliente", max_length=300, blank=True)

    pago_em = models.DateTimeField(null=True, blank=True)
    separado_em = models.DateTimeField("em separação desde", null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-criado_em"]
        # DSQL indexes have no sort direction; the index is read backwards for "-criado_em".
        indexes = [models.Index(fields=["cliente", "criado_em"])]
        constraints = [
            models.CheckConstraint(condition=Q(total_centavos__gte=0), name="pedido_total_valido"),
            models.CheckConstraint(
                condition=Q(parcelas__gte=1, parcelas__lte=12), name="pedido_parcelas_validas"
            ),
        ]

    def __str__(self):
        return self.codigo

    def get_absolute_url(self):
        return reverse("pedidos:detalhe", kwargs={"codigo": self.codigo})

    @property
    def data_do_status(self) -> dict:
        return {
            self.Status.PAGO: self.pago_em,
            self.Status.EM_SEPARACAO: self.separado_em,
            self.Status.ENVIADO: self.enviado_em,
            self.Status.ENTREGUE: self.entregue_em,
        }

    def linha_do_tempo(self) -> list[dict]:
        """Steps for the customer's page: done, current or pending."""
        datas = self.data_do_status
        atual = self.ETAPAS.index(self.status) if self.status in self.ETAPAS else -1
        etapas = []
        for indice, etapa in enumerate(self.ETAPAS):
            if self.status == self.Status.CANCELADO:
                estado = "concluida" if datas[etapa] else "pendente"
            elif indice < atual:
                estado = "concluida"
            elif indice == atual:
                estado = "atual" if etapa != self.Status.ENTREGUE else "concluida"
            else:
                estado = "pendente"
            etapas.append(
                {"status": etapa, "nome": etapa.label, "data": datas[etapa], "estado": estado}
            )
        return etapas

    @property
    def endereco_resumo(self) -> str:
        e = self.endereco_entrega
        complemento = f" ({e['complemento']})" if e.get("complemento") else ""
        return (
            f"{e['logradouro']}, {e['numero']}{complemento}, {e['bairro']}, "
            f"{e['cidade']}/{e['uf']}, CEP {e['cep'][:5]}-{e['cep'][5:]}"
        )

    @property
    def pode_avaliar(self) -> bool:
        return self.status == self.Status.ENTREGUE


class PedidoItem(models.Model):
    """Copy of the product at purchase time: price and name don't change afterwards."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(
        "catalogo.Produto", on_delete=models.PROTECT, related_name="itens_pedido"
    )
    variacao = models.ForeignKey(
        "catalogo.ProdutoVariacao", on_delete=models.PROTECT, related_name="itens_pedido"
    )
    nome = models.CharField(max_length=80)
    detalhes = models.CharField("variação", max_length=80, blank=True)
    sku = models.CharField("SKU", max_length=40)
    preco_unitario_centavos = models.BigIntegerField("preço unitário (centavos)")
    quantidade = models.PositiveSmallIntegerField()
    sob_encomenda = models.BooleanField(default=False)
    reservado = models.BooleanField(
        default=False, help_text="Se a unidade foi reservada no estoque ao criar o pedido."
    )

    class Meta:
        verbose_name = "item"
        verbose_name_plural = "itens"
        constraints = [
            models.CheckConstraint(condition=Q(quantidade__gt=0), name="item_quantidade_positiva"),
        ]

    def __str__(self):
        return f"{self.quantidade}× {self.nome}"

    @property
    def total_centavos(self) -> int:
        return self.preco_unitario_centavos * self.quantidade
