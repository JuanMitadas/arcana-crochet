"""Regras de estoque. Nada altera ``ProdutoVariacao.estoque`` fora deste módulo."""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MovimentacaoEstoque, Produto, ProdutoVariacao


class EstoqueInsuficiente(ValidationError):
    pass


@transaction.atomic
def registrar_movimentacao(
    variacao: ProdutoVariacao,
    tipo: str,
    quantidade: int,
    autor=None,
    motivo: str = "",
) -> MovimentacaoEstoque:
    """Aplica uma entrada (quantidade > 0) ou saída (< 0) e grava o histórico.

    A linha da variação é travada (SELECT ... FOR UPDATE) para que duas vendas
    simultâneas da mesma peça única nunca deixem o estoque negativo.
    """
    if quantidade == 0:
        raise ValidationError("A quantidade não pode ser zero.")

    travada = ProdutoVariacao.objects.select_for_update().get(pk=variacao.pk)
    novo_estoque = travada.estoque + quantidade
    if novo_estoque < travada.estoque_reservado:
        raise EstoqueInsuficiente(
            f"Estoque insuficiente para {travada}: há {travada.disponivel} disponível(is)."
        )

    travada.estoque = novo_estoque
    travada.save(update_fields=["estoque", "atualizado_em"])
    variacao.estoque = novo_estoque

    movimentacao = MovimentacaoEstoque.objects.create(
        variacao=travada,
        tipo=tipo,
        quantidade=quantidade,
        estoque_resultante=novo_estoque,
        autor=autor,
        motivo=motivo,
    )
    atualizar_status_esgotado(travada.produto_id)
    return movimentacao


def atualizar_status_esgotado(produto_id) -> None:
    """Marca o produto como esgotado quando nenhuma variação ativa tem estoque, e o
    reativa quando o estoque volta. Rascunhos, pausados e arquivados não mudam."""
    produto = Produto.objects.select_for_update().get(pk=produto_id)
    tem_estoque = any(v.disponivel > 0 for v in produto.variacoes.filter(ativa=True))
    sob_encomenda = produto.disponibilidade == Produto.Disponibilidade.SOB_ENCOMENDA

    if produto.status == Produto.Status.ATIVO and not tem_estoque and not sob_encomenda:
        produto.status = Produto.Status.ESGOTADO
        produto.save(update_fields=["status", "atualizado_em"])
    elif produto.status == Produto.Status.ESGOTADO and (tem_estoque or sob_encomenda):
        produto.status = Produto.Status.ATIVO
        produto.save(update_fields=["status", "atualizado_em"])
