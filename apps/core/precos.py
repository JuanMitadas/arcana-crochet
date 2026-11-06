"""Pricing rules shown in the store: Pix discount and interest-free installments."""

from dataclasses import dataclass
from math import ceil

from django.conf import settings


def _loja(chave):
    return settings.LOJA[chave]


def preco_pix(centavos: int) -> int:
    """Price with the Pix discount, rounded to the cent."""
    # Rounds half a cent up (same as Math.round in the store's JavaScript).
    return (centavos * (100 - _loja("PIX_DESCONTO_PCT")) + 50) // 100


@dataclass(frozen=True)
class Parcelamento:
    vezes: int
    valor_parcela_centavos: int


def parcelamento(centavos: int) -> Parcelamento:
    """Largest number of interest-free installments that respects the minimum installment."""
    maximo = _loja("PARCELAS_SEM_JUROS")
    minima = _loja("PARCELA_MINIMA_CENTAVOS")
    vezes = 1
    for n in range(maximo, 0, -1):
        if centavos / n >= minima:
            vezes = n
            break
    return Parcelamento(vezes=vezes, valor_parcela_centavos=ceil(centavos / vezes))


def opcoes_parcelamento(centavos: int) -> list[Parcelamento]:
    """Every option from 1x up to the maximum allowed for the amount."""
    maximo = parcelamento(centavos).vezes
    return [Parcelamento(n, ceil(centavos / n)) for n in range(1, maximo + 1)]


def percentual_desconto(preco_centavos: int, promocional_centavos: int | None) -> int:
    if not promocional_centavos or promocional_centavos >= preco_centavos:
        return 0
    return round((preco_centavos - promocional_centavos) * 100 / preco_centavos)
