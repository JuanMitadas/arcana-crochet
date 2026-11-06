"""Keep ``Produto.busca`` in sync when related rows change."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Categoria, Produto, ProdutoVariacao


@receiver([post_save, post_delete], sender=ProdutoVariacao)
def variacao_alterada(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and "cor" not in update_fields:
        return  # stock updates do not change the search text
    produto = Produto.objects.filter(pk=instance.produto_id).first()
    if produto:
        produto.atualizar_busca()


@receiver(post_save, sender=Categoria)
def categoria_alterada(sender, instance, created, **kwargs):
    if created:
        return
    for produto in Produto.objects.filter(categoria__in=[instance, *instance.filhas.all()]):
        produto.atualizar_busca()
