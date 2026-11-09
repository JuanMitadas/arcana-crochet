"""Pix straight to the store's account, with no payment provider and no fees.

The order page shows a static Pix QR code and its "copia e cola" text with the order
amount, built from the Banco Central's BR Code standard (EMV QR Code). The money lands
in the store's bank account; nobody tells the site, so the store checks the bank app
and approves the payment in the admin ("Aprovar pagamento"). Orders not paid within
``LOJA_PIX_PRAZO_HORAS`` are cancelled by ``servicos.cancelar_vencidos``.
"""

import re

import segno
from django.conf import settings

from apps.core.texto import normalizar


def _campo(identificador: str, valor: str) -> str:
    return f"{identificador}{len(valor):02d}{valor}"


def crc16(dados: str) -> str:
    """CRC16-CCITT (polynomial 0x1021, initial 0xFFFF), as the BR Code requires."""
    crc = 0xFFFF
    for byte in dados.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _texto_simples(texto: str, limite: int) -> str:
    """Uppercase ASCII without accents, as banks expect in the name and city fields."""
    return re.sub(r"[^A-Z0-9 ]", "", normalizar(texto).upper())[:limite].strip()


def copia_e_cola(chave: str, recebedor: str, cidade: str, valor_centavos: int, txid: str) -> str:
    """Pix "copia e cola" text (BR Code) for a one-off payment of a fixed amount."""
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave.strip())
    payload = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")  # BRL
        + _campo("54", f"{valor_centavos / 100:.2f}")
        + _campo("58", "BR")
        + _campo("59", _texto_simples(recebedor, 25))
        + _campo("60", _texto_simples(cidade, 15))
        + _campo("62", _campo("05", re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"))
        + "6304"
    )
    return payload + crc16(payload)


def configurado() -> bool:
    loja = settings.LOJA
    return bool(loja["PIX_CHAVE"] and loja["PIX_RECEBEDOR"] and loja["PIX_CIDADE"])


def cobranca(pedido) -> dict | None:
    """Text and QR code (inline SVG) to pay the order, or None if Pix isn't set up."""
    if not configurado():
        return None
    loja = settings.LOJA
    texto = copia_e_cola(
        loja["PIX_CHAVE"], loja["PIX_RECEBEDOR"], loja["PIX_CIDADE"],
        pedido.total_centavos, pedido.codigo,
    )  # fmt: skip
    qr = segno.make(texto, error="m")
    svg = qr.svg_inline(
        scale=4, border=2, dark="#034947", light="#fffef6", omitsize=True, svgclass="w-full h-auto"
    )
    return {"copia_e_cola": texto, "qr_svg": svg}
