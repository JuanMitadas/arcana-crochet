"""Shipping quotes.

Until the Melhor Envio integration lands, shipping is estimated from a table by the
destination CEP's region, starting from Cotia/SP. The interface (``cotar(cep, itens)``
returning a list of ``OpcaoFrete``) is the one the real quote will use, so the pages
don't change when it arrives.
"""

from dataclasses import dataclass
from math import ceil

from django.conf import settings

EMBALAGEM_G = 120

# (region, PAC base, PAC per extra kg, PAC days, SEDEX base, SEDEX per extra kg, SEDEX days)
# Amounts in cents, lead times in business days. The CEP's first digit sets the region.
TABELA = {
    "0": ("São Paulo capital e região", 1890, 350, 4, 2690, 600, 1),
    "1": ("Interior de São Paulo", 2190, 400, 5, 3190, 700, 2),
    "2": ("Rio de Janeiro e Espírito Santo", 2590, 500, 6, 3990, 900, 2),
    "3": ("Minas Gerais", 2490, 500, 6, 3790, 900, 2),
    "4": ("Bahia e Sergipe", 3290, 700, 9, 5490, 1300, 4),
    "5": ("Pernambuco, Alagoas, Paraíba e Rio Grande do Norte", 3590, 800, 10, 5990, 1500, 4),
    "6": ("Ceará, Piauí, Maranhão e região Norte", 3890, 900, 12, 6590, 1700, 5),
    "7": ("Centro-Oeste, Tocantins, Rondônia e Acre", 3190, 700, 8, 5290, 1300, 3),
    "8": ("Paraná e Santa Catarina", 2590, 500, 6, 3990, 900, 2),
    "9": ("Rio Grande do Sul", 2790, 600, 7, 4290, 1000, 3),
}


@dataclass(frozen=True)
class OpcaoFrete:
    codigo: str
    nome: str
    preco_centavos: int
    prazo_dias: int
    gratis: bool = False

    @property
    def descricao_prazo(self) -> str:
        if self.prazo_dias == 1:
            return "1 dia útil"
        return f"{self.prazo_dias} dias úteis"


def limpar_cep(cep: str) -> str:
    return "".join(c for c in (cep or "") if c.isdigit())


def cep_valido(cep: str) -> bool:
    return len(limpar_cep(cep)) == 8


def regiao(cep: str) -> str:
    return TABELA[limpar_cep(cep)[0]][0]


def cotar(cep: str, peso_total_g: int, subtotal_centavos: int, prazo_extra_dias: int = 0):
    """Delivery options for the CEP. ``prazo_extra_dias`` adds the production time of
    made-to-order pieces. Raises ValueError for an invalid CEP."""
    cep = limpar_cep(cep)
    if len(cep) != 8:
        raise ValueError("Digite um CEP com 8 números.")

    _, pac, pac_kg, pac_prazo, sedex, sedex_kg, sedex_prazo = TABELA[cep[0]]
    kg_extras = max(0, ceil((peso_total_g + EMBALAGEM_G) / 1000) - 1)
    limite_gratis = settings.LOJA["FRETE_GRATIS_A_PARTIR_CENTAVOS"]
    gratis = bool(limite_gratis) and subtotal_centavos >= limite_gratis

    return [
        OpcaoFrete(
            "pac",
            "PAC",
            0 if gratis else pac + kg_extras * pac_kg,
            pac_prazo + prazo_extra_dias,
            gratis=gratis,
        ),
        OpcaoFrete("sedex", "SEDEX", sedex + kg_extras * sedex_kg, sedex_prazo + prazo_extra_dias),
    ]
