"""Order lifecycle rules. Views and the admin only call these functions.

Each one is an ``atomico`` transaction: on Aurora DSQL a conflict with another
transaction (two people buying the last piece) makes it run again from the start."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone

from apps.catalogo.estoque import atualizar_status_esgotado, registrar_movimentacao
from apps.catalogo.models import MovimentacaoEstoque, ProdutoVariacao
from apps.core import precos
from apps.core.transacoes import atomico

from .carrinho import Carrinho
from .models import Cupom, Pedido, PedidoItem

logger = logging.getLogger(__name__)


class TransicaoInvalida(ValidationError):
    pass


@atomico
def criar_pedido(
    cliente, carrinho: Carrinho, endereco, metodo: str, parcelas: int = 1, observacao: str = ""
) -> Pedido:
    """Turn the bag into an order awaiting payment.

    Ready-to-ship pieces are reserved (no longer shown as available to anyone else)
    until the payment is approved or the order is cancelled.
    """
    itens = carrinho.itens
    if not itens:
        raise ValidationError("Sua sacola está vazia.")
    if carrinho.ajustado:
        raise ValidationError(
            "Alguns itens da sacola mudaram de disponibilidade. Confira antes de continuar."
        )
    opcao_frete = carrinho.frete
    if opcao_frete is None:
        raise ValidationError("Informe o CEP para calcular o frete.")

    travadas = {
        v.pk: v
        for v in ProdutoVariacao.objects.select_for_update()
        .filter(pk__in=[i.variacao.pk for i in itens])
        .order_by("pk")
    }
    for item in itens:
        variacao = travadas[item.variacao.pk]
        if not item.sob_encomenda and variacao.disponivel < item.quantidade:
            raise ValidationError(f"{item.produto.nome} acabou de esgotar. Atualize sua sacola.")

    subtotal = carrinho.subtotal_centavos
    desconto_cupom = carrinho.desconto_cupom_centavos
    base = subtotal - desconto_cupom
    desconto_pix = base - precos.preco_pix(base) if metodo == Pedido.Metodo.PIX else 0
    if metodo == Pedido.Metodo.CARTAO:
        maximo = precos.parcelamento(base + opcao_frete.preco_centavos).vezes
        parcelas = max(1, min(int(parcelas or 1), maximo))
    else:
        parcelas = 1

    pedido = Pedido.objects.create(
        cliente=cliente,
        metodo_pagamento=metodo,
        parcelas=parcelas,
        subtotal_centavos=subtotal,
        desconto_cupom_centavos=desconto_cupom,
        desconto_pix_centavos=desconto_pix,
        frete_centavos=opcao_frete.preco_centavos,
        total_centavos=base - desconto_pix + opcao_frete.preco_centavos,
        cupom=carrinho.cupom_valido,
        endereco_entrega=endereco.como_dict(),
        frete_servico=opcao_frete.nome,
        frete_prazo_dias=opcao_frete.prazo_dias,
        observacao=observacao,
    )

    for item in itens:
        variacao = travadas[item.variacao.pk]
        reservar = not item.sob_encomenda
        PedidoItem.objects.create(
            pedido=pedido,
            produto=item.produto,
            variacao=variacao,
            nome=item.produto.nome,
            detalhes=item.detalhes,
            sku=variacao.sku,
            preco_unitario_centavos=item.preco_unitario_centavos,
            quantidade=item.quantidade,
            sob_encomenda=item.sob_encomenda,
            reservado=reservar,
        )
        if reservar:
            variacao.estoque_reservado += item.quantidade
            variacao.save(update_fields=["estoque_reservado", "atualizado_em"])

    for produto_id in {i.produto.pk for i in itens}:
        atualizar_status_esgotado(produto_id)
    if pedido.cupom_id:
        Cupom.objects.filter(pk=pedido.cupom_id).update(usos=F("usos") + 1)

    carrinho.limpar()
    return pedido


def _travar(pedido: Pedido) -> Pedido:
    return Pedido.objects.select_for_update().get(pk=pedido.pk)


def _liberar_reserva(item: PedidoItem) -> ProdutoVariacao:
    variacao = ProdutoVariacao.objects.select_for_update().get(pk=item.variacao_id)
    variacao.estoque_reservado = max(0, variacao.estoque_reservado - item.quantidade)
    variacao.save(update_fields=["estoque_reservado", "atualizado_em"])
    return variacao


@atomico
def marcar_pago(pedido: Pedido) -> Pedido:
    """Payment approved: the reservation becomes a final stock deduction."""
    pedido = _travar(pedido)
    if pedido.status != Pedido.Status.AGUARDANDO_PAGAMENTO:
        raise TransicaoInvalida(f"O pedido {pedido} não está aguardando pagamento.")
    for item in pedido.itens.filter(reservado=True):
        variacao = _liberar_reserva(item)
        registrar_movimentacao(
            variacao, MovimentacaoEstoque.Tipo.VENDA, -item.quantidade, motivo=f"Pedido {pedido}"
        )
    pedido.status = Pedido.Status.PAGO
    pedido.pago_em = timezone.now()
    pedido.save(update_fields=["status", "pago_em", "atualizado_em"])
    return pedido


@atomico
def avancar(pedido: Pedido, codigo_rastreio: str = "", transportadora: str = "") -> Pedido:
    """Paid → Being prepared → Shipped (requires tracking) → Delivered."""
    pedido = _travar(pedido)
    proximo = Pedido.PROXIMO.get(pedido.status)
    if proximo is None:
        raise TransicaoInvalida(
            f"O pedido {pedido} não pode avançar de “{pedido.get_status_display()}”."
        )
    agora = timezone.now()
    campos = ["status", "atualizado_em"]
    if proximo == Pedido.Status.EM_SEPARACAO:
        pedido.separado_em = agora
        campos.append("separado_em")
    elif proximo == Pedido.Status.ENVIADO:
        codigo_rastreio = (codigo_rastreio or pedido.codigo_rastreio).strip().upper()
        if not codigo_rastreio:
            raise TransicaoInvalida("Informe o código de rastreio para marcar como enviado.")
        pedido.codigo_rastreio = codigo_rastreio
        pedido.transportadora = transportadora or pedido.transportadora or "Correios"
        pedido.enviado_em = agora
        campos += ["codigo_rastreio", "transportadora", "enviado_em"]
    else:
        pedido.entregue_em = agora
        campos.append("entregue_em")
    pedido.status = proximo
    pedido.save(update_fields=campos)
    return pedido


@atomico
def cancelar(pedido: Pedido, motivo: str = "") -> Pedido:
    """Cancel before shipping and return the pieces to stock."""
    pedido = _travar(pedido)
    if pedido.status not in (
        Pedido.Status.AGUARDANDO_PAGAMENTO,
        Pedido.Status.PAGO,
        Pedido.Status.EM_SEPARACAO,
    ):
        raise TransicaoInvalida("Só é possível cancelar pedidos que ainda não foram enviados.")
    estava_pago = pedido.status != Pedido.Status.AGUARDANDO_PAGAMENTO
    for item in pedido.itens.filter(reservado=True):
        if estava_pago:
            registrar_movimentacao(
                item.variacao,
                MovimentacaoEstoque.Tipo.CANCELAMENTO,
                item.quantidade,
                motivo=motivo or f"Cancelamento do pedido {pedido}",
            )
        else:
            _liberar_reserva(item)
            atualizar_status_esgotado(item.produto_id)
    pedido.status = Pedido.Status.CANCELADO
    pedido.cancelado_em = timezone.now()
    pedido.save(update_fields=["status", "cancelado_em", "atualizado_em"])
    return pedido


def cancelar_vencidos() -> int:
    """Cancel orders still awaiting payment after the deadline. Returns how many.

    Runs every hour (EventBridge → /healthz/, see apps/core/views.py) and with
    ``python manage.py cancelar_pedidos_vencidos``. Each order is its own transaction.
    """
    limite = timezone.now() - timedelta(hours=settings.LOJA["PRAZO_PAGAMENTO_HORAS"])
    vencidos = Pedido.objects.filter(
        status=Pedido.Status.AGUARDANDO_PAGAMENTO, criado_em__lt=limite
    ).values_list("pk", flat=True)
    cancelados = sum(_cancelar_se_vencido(pk, limite) for pk in list(vencidos))
    if cancelados:
        logger.info("Cancelled %s unpaid order(s) past the deadline", cancelados)
    return cancelados


@atomico
def _cancelar_se_vencido(pk, limite) -> bool:
    # Checked again under the lock: the payment may have been approved meanwhile, and
    # cancelar() would also cancel a paid order.
    pedido = Pedido.objects.select_for_update().get(pk=pk)
    if pedido.status != Pedido.Status.AGUARDANDO_PAGAMENTO or pedido.criado_em >= limite:
        return False
    cancelar(pedido, motivo="Pagamento não recebido no prazo")
    return True
