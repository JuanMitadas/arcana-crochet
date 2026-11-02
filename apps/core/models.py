from django.db import models

from .ids import uuid7


class ModeloBase(models.Model):
    """Base de todas as tabelas: id UUID v7 e datas de criação e atualização."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-criado_em"]
