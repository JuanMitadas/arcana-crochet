"""Regras do ciclo de vida do pedido. As views e o painel chamam só estas funções."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalogo.estoque import atualizar_status_esgotado, registrar_movimentacao
from apps.catalogo.models import MovimentacaoEstoque, ProdutoVariacao
from apps.core import precos

from .carrinho import Carrinho
from .models import Cupom, Pedido, PedidoItem


class TransicaoInvalida(ValidationError):
    pass


@transaction.atomic
def criar_pedido(
    cliente, carrinho: Carrinho, endereco, metodo: str, parcelas: int = 1, observacao: str = ""
) -> Pedido:
    """Fecha a sacola em um pedido aguardando pagamento.

    Peças de pronta entrega ficam reservadas (não aparecem como disponíveis para
    outra pessoa) até o pagamento ser aprovado ou o pedido ser cancelado.
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


@transaction.atomic
def marcar_pago(pedido: Pedido) -> Pedido:
    """Pagamento aprovado: a reserva vira baixa definitiva no estoque."""
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


@transaction.atomic
def avancar(pedido: Pedido, codigo_rastreio: str = "", transportadora: str = "") -> Pedido:
    """Pago → Em separação → Enviado (exige rastreio) → Entregue."""
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


@transaction.atomic
def cancelar(pedido: Pedido, motivo: str = "") -> Pedido:
    """Cancela antes do envio e devolve as peças ao estoque."""
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
