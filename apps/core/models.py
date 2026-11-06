from django.db import models

from .ids import uuid7


class ModeloBase(models.Model):
    """Base for every table: UUID v7 id plus created and updated timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-criado_em"]


class EntradaCache(models.Model):
    """Table for Django's DatabaseCache (``CACHE_URL=dbcache://cache_django``).

    Declared as a model so the table is created by a regular migration:
    ``createcachetable`` runs several DDL statements in one transaction, which Aurora
    DSQL does not allow. Columns match what ``DatabaseCache`` expects.
    """

    cache_key = models.CharField(max_length=255, primary_key=True)
    value = models.TextField()
    expires = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "cache_django"
        verbose_name = "entrada de cache"
        verbose_name_plural = "cache"

    def __str__(self):
        return self.cache_key
