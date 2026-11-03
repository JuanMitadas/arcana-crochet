from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import ModeloBase


class Avaliacao(ModeloBase):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Aguardando moderação"
        PUBLICADA = "publicada", "Publicada"
        OCULTA = "oculta", "Oculta"

    produto = models.ForeignKey(
        "catalogo.Produto", on_delete=models.CASCADE, related_name="avaliacoes"
    )
    item = models.OneToOneField(
        "pedidos.PedidoItem",
        verbose_name="item do pedido",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacao",
        help_text="Compra que originou a avaliação. Só quem recebeu a peça pode avaliar.",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    nota = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    titulo = models.CharField("título", max_length=80, blank=True)
    comentario = models.TextField("comentário", max_length=2000, blank=True)
    resposta_loja = models.TextField("resposta da loja", max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nota__gte=1, nota__lte=5), name="avaliacao_nota_1_a_5"
            ),
        ]

    def __str__(self):
        return f"{self.nota}★ {self.produto} por {self.autor}"

    @property
    def nome_autor(self) -> str:
        usuario = self.autor
        if usuario.nome_exibicao:
            return usuario.nome_exibicao
        if usuario.nome_completo:
            partes = usuario.nome_completo.split()
            return f"{partes[0]} {partes[-1][0]}." if len(partes) > 1 else partes[0]
        return "Cliente Arcana"

    @property
    def compra_verificada(self) -> bool:
        return self.item_id is not None
