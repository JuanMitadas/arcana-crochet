"""Regras de preço exibidas na loja: desconto no Pix e parcelamento sem juros."""

from dataclasses import dataclass
from math import ceil

from django.conf import settings


def _loja(chave):
    return settings.LOJA[chave]


def preco_pix(centavos: int) -> int:
    """Preço com o desconto do Pix, arredondado para o centavo."""
    # Arredonda meio centavo para cima (igual ao Math.round do JavaScript da loja).
    return (centavos * (100 - _loja("PIX_DESCONTO_PCT")) + 50) // 100


@dataclass(frozen=True)
class Parcelamento:
    vezes: int
    valor_parcela_centavos: int


def parcelamento(centavos: int) -> Parcelamento:
    """Maior número de parcelas sem juros que respeita a parcela mínima."""
    maximo = _loja("PARCELAS_SEM_JUROS")
    minima = _loja("PARCELA_MINIMA_CENTAVOS")
    vezes = 1
    for n in range(maximo, 0, -1):
        if centavos / n >= minima:
            vezes = n
            break
    return Parcelamento(vezes=vezes, valor_parcela_centavos=ceil(centavos / vezes))


def opcoes_parcelamento(centavos: int) -> list[Parcelamento]:
    """Todas as opções de 1x até o máximo permitido para o valor."""
    maximo = parcelamento(centavos).vezes
    return [Parcelamento(n, ceil(centavos / n)) for n in range(1, maximo + 1)]


def percentual_desconto(preco_centavos: int, promocional_centavos: int | None) -> int:
    if not promocional_centavos or promocional_centavos >= preco_centavos:
        return 0
    return round((preco_centavos - promocional_centavos) * 100 / preco_centavos)
