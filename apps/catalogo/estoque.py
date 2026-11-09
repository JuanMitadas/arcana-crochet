"""Stock rules. Nothing outside this module changes ``ProdutoVariacao.estoque``."""

from django.core.exceptions import ValidationError

from apps.core.transacoes import atomico

from .models import MovimentacaoEstoque, Produto, ProdutoVariacao


class EstoqueInsuficiente(ValidationError):
    pass


@atomico
def registrar_movimentacao(
    variacao: ProdutoVariacao,
    tipo: str,
    quantidade: int,
    autor=None,
    motivo: str = "",
) -> MovimentacaoEstoque:
    """Apply an incoming (quantity > 0) or outgoing (< 0) movement and record it.

    The variation row is locked (SELECT ... FOR UPDATE) so two simultaneous sales of
    the same one-of-a-kind piece never leave the stock negative. On Aurora DSQL the
    lock becomes an optimistic conflict and ``atomico`` runs the loser again.
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
    """Mark the product as sold out when no active variation has stock, and bring it
    back when stock returns. Drafts, paused and archived products don't change."""
    produto = Produto.objects.select_for_update().get(pk=produto_id)
    tem_estoque = any(v.disponivel > 0 for v in produto.variacoes.filter(ativa=True))
    sob_encomenda = produto.disponibilidade == Produto.Disponibilidade.SOB_ENCOMENDA

    if produto.status == Produto.Status.ATIVO and not tem_estoque and not sob_encomenda:
        produto.status = Produto.Status.ESGOTADO
        produto.save(update_fields=["status", "atualizado_em"])
    elif produto.status == Produto.Status.ESGOTADO and (tem_estoque or sob_encomenda):
        produto.status = Produto.Status.ATIVO
        produto.save(update_fields=["status", "atualizado_em"])
