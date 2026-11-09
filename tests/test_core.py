import pytest

from apps.core.ids import _uuid7_fallback
from apps.core.templatetags.dinheiro import brl


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (0, "R$ 0,00"),
        (5, "R$ 0,05"),
        (12_990, "R$ 129,90"),
        (123_456_789, "R$ 1.234.567,89"),
        (-1_050, "-R$ 10,50"),
        (None, ""),
    ],
)
def test_brl_formata_centavos(centavos, esperado):
    assert brl(centavos) == esperado


def test_uuid7_tem_versao_e_variante_corretas():
    valor = _uuid7_fallback()
    assert valor.version == 7
    assert valor.variant == "specified in RFC 4122"


def test_uuid7_e_ordenavel_pelo_tempo():
    import time

    primeiro = _uuid7_fallback()
    time.sleep(0.002)
    segundo = _uuid7_fallback()
    assert primeiro < segundo


def test_healthz_responde_ok(client, db):
    resposta = client.get("/healthz/")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_paginas_tem_politica_de_seguranca_de_conteudo(client, db):
    resposta = client.get("/sobre/")
    assert resposta.status_code == 200
    assert "script-src 'self' 'nonce-" in resposta["Content-Security-Policy"]
    assert resposta["X-Frame-Options"] == "DENY"
