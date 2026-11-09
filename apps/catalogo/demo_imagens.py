"""Demo illustrations with a crochet texture, drawn with Pillow.

They only fill the store during development until the real photos arrive. Each
piece is a simple shape filled with rows of stitches.
"""

import io
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

LARGURA, ALTURA = 900, 1125
FUNDOS = ["#dde9e6", "#dbe7ee", "#f4f0d6", "#e6ece4", "#ece6dc"]


def _hex(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i : i + 2], 16) for i in (0, 2, 4))


def _misturar(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def textura_croche(cor, tamanho=(LARGURA, ALTURA), passo=22, seed=0):
    """Rows of "V" stitches, like the crochet single stitch."""
    rnd = random.Random(seed)
    base = _hex(cor)
    clara = _misturar(base, (255, 255, 255), 0.28)
    escura = _misturar(base, (0, 0, 0), 0.32)
    img = Image.new("RGB", tamanho, _misturar(base, (0, 0, 0), 0.12))
    d = ImageDraw.Draw(img)
    alto = int(passo * 0.9)
    for linha, y in enumerate(range(-passo, tamanho[1] + passo, alto)):
        deslocamento = (passo // 2) if linha % 2 else 0
        for x in range(-passo, tamanho[0] + passo, passo):
            cx = x + deslocamento + rnd.randint(-1, 1)
            cy = y + rnd.randint(-1, 1)
            tom = _misturar(base, clara, rnd.uniform(0.1, 0.6))
            meia = passo // 2
            # the two "legs" of the V
            d.ellipse([cx - meia + 1, cy - 2, cx, cy + alto - 2], fill=tom)
            d.ellipse([cx, cy - 2, cx + meia - 1, cy + alto - 2], fill=_misturar(tom, base, 0.35))
            d.line([cx, cy + 1, cx, cy + alto - 4], fill=escura, width=2)
    return img.filter(ImageFilter.GaussianBlur(0.6))


# --- Shapes (grayscale masks) ---------------------------------------------


def _mascara():
    return Image.new("L", (LARGURA, ALTURA), 0)


def forma_urso():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.ellipse([250, 520, 650, 960], fill=255)  # body
    d.ellipse([255, 230, 645, 610], fill=255)  # head
    d.ellipse([245, 205, 365, 325], fill=255)  # ears
    d.ellipse([535, 205, 655, 325], fill=255)
    d.ellipse([185, 600, 305, 760], fill=255)  # arms
    d.ellipse([595, 600, 715, 760], fill=255)
    d.ellipse([270, 860, 420, 990], fill=255)  # feet
    d.ellipse([480, 860, 630, 990], fill=255)
    return m


def detalhes_urso(img, cor):
    d = ImageDraw.Draw(img)
    claro = _misturar(_hex(cor), (255, 255, 255), 0.55)
    d.ellipse([385, 420, 515, 520], fill=claro)  # snout
    d.ellipse([430, 435, 470, 462], fill=(40, 34, 32))
    d.ellipse([345, 375, 375, 410], fill=(30, 28, 28))
    d.ellipse([525, 375, 555, 410], fill=(30, 28, 28))
    d.arc([420, 455, 480, 495], 20, 160, fill=(40, 34, 32), width=4)
    d.ellipse([320, 430, 360, 455], fill=(232, 160, 160))
    d.ellipse([540, 430, 580, 455], fill=(232, 160, 160))


def forma_coelho():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.ellipse([270, 560, 630, 970], fill=255)
    d.ellipse([280, 330, 620, 640], fill=255)
    d.rounded_rectangle([320, 80, 410, 400], radius=45, fill=255)
    d.rounded_rectangle([490, 80, 580, 400], radius=45, fill=255)
    d.ellipse([290, 880, 430, 990], fill=255)
    d.ellipse([470, 880, 610, 990], fill=255)
    return m


def detalhes_coelho(img, cor):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([345, 120, 385, 360], radius=20, fill=(236, 186, 186))
    d.rounded_rectangle([515, 120, 555, 360], radius=20, fill=(236, 186, 186))
    d.ellipse([370, 460, 398, 492], fill=(30, 28, 28))
    d.ellipse([502, 460, 530, 492], fill=(30, 28, 28))
    d.polygon([(435, 515), (465, 515), (450, 532)], fill=(200, 120, 120))
    d.ellipse([335, 515, 375, 540], fill=(236, 170, 170))
    d.ellipse([525, 515, 565, 540], fill=(236, 170, 170))


def forma_polvo():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.ellipse([230, 240, 670, 700], fill=255)
    for i in range(6):
        x = 250 + i * 72
        d.rounded_rectangle([x, 560, x + 62, 930 - (i % 2) * 50], radius=31, fill=255)
        d.ellipse([x - 10, 860 - (i % 2) * 50, x + 70, 940 - (i % 2) * 50], fill=255)
    return m


def detalhes_polvo(img, cor):
    d = ImageDraw.Draw(img)
    d.ellipse([360, 450, 392, 486], fill=(30, 28, 28))
    d.ellipse([508, 450, 540, 486], fill=(30, 28, 28))
    d.arc([420, 470, 480, 520], 20, 160, fill=(40, 34, 32), width=4)
    d.ellipse([320, 500, 365, 528], fill=(236, 170, 170))
    d.ellipse([535, 500, 580, 528], fill=(236, 170, 170))


def forma_baleia():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.ellipse([150, 420, 690, 860], fill=255)
    d.polygon([(640, 620), (800, 470), (830, 560), (760, 640), (840, 720), (800, 790)], fill=255)
    d.ellipse([360, 800, 470, 880], fill=255)
    return m


def detalhes_baleia(img, cor):
    d = ImageDraw.Draw(img)
    claro = _misturar(_hex(cor), (255, 255, 255), 0.6)
    d.chord([170, 560, 670, 860], 0, 180, fill=claro)
    d.ellipse([300, 580, 330, 615], fill=(30, 28, 28))
    d.arc([300, 620, 380, 680], 10, 130, fill=(40, 34, 32), width=4)
    for i, dx in enumerate((-30, 0, 30)):
        d.line([420, 410, 420 + dx * 1.6, 300 - (i % 2) * 20], fill=(150, 200, 220), width=10)


def forma_estrela():
    m = _mascara()
    d = ImageDraw.Draw(m)
    cx, cy, externo, interno = 450, 560, 340, 150
    pontos = []
    for i in range(10):
        r = externo if i % 2 == 0 else interno
        a = -math.pi / 2 + i * math.pi / 5
        pontos.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pontos, fill=255)
    return m.filter(ImageFilter.GaussianBlur(10)).point(lambda p: 255 if p > 110 else 0)


def detalhes_estrela(img, cor):
    d = ImageDraw.Draw(img)
    d.ellipse([400, 540, 425, 570], fill=(30, 28, 28))
    d.ellipse([475, 540, 500, 570], fill=(30, 28, 28))
    d.arc([425, 565, 475, 600], 20, 160, fill=(40, 34, 32), width=4)
    d.line([450, 190, 450, 60], fill=(120, 110, 100), width=4)
    d.ellipse([425, 40, 475, 90], outline=(120, 110, 100), width=6)


def forma_cesto():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.polygon([(190, 420), (710, 420), (650, 930), (250, 930)], fill=255)
    d.ellipse([190, 380, 710, 470], fill=255)
    d.ellipse([250, 880, 650, 970], fill=255)
    return m


def detalhes_cesto(img, cor):
    d = ImageDraw.Draw(img)
    d.ellipse([215, 395, 685, 455], fill=_misturar(_hex(cor), (0, 0, 0), 0.4))
    for y in (500, 520):
        d.line([200, y, 700, y], fill=_misturar(_hex(cor), (0, 0, 0), 0.2), width=6)
    d.rounded_rectangle([170, 470, 230, 520], radius=20, outline=(60, 50, 40), width=10)
    d.rounded_rectangle([670, 470, 730, 520], radius=20, outline=(60, 50, 40), width=10)


def forma_bolsa():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([200, 470, 700, 940], radius=90, fill=255)
    return m


def detalhes_bolsa(img, cor):
    d = ImageDraw.Draw(img)
    escura = _misturar(_hex(cor), (0, 0, 0), 0.35)
    d.arc([270, 170, 630, 640], 190, 350, fill=escura, width=26)
    d.rounded_rectangle([200, 470, 700, 560], radius=40, fill=_misturar(_hex(cor), (0, 0, 0), 0.18))
    d.ellipse([430, 560, 470, 600], fill=(212, 178, 112))


def forma_gorro():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.chord([190, 300, 710, 1000], 180, 360, fill=255)
    d.rounded_rectangle([180, 620, 720, 800], radius=40, fill=255)
    d.ellipse([370, 150, 530, 310], fill=255)
    return m


def detalhes_gorro(img, cor):
    d = ImageDraw.Draw(img)
    escura = _misturar(_hex(cor), (0, 0, 0), 0.22)
    for x in range(200, 720, 34):
        d.line([x, 630, x, 790], fill=escura, width=5)


def forma_porta_copos():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.ellipse([170, 290, 730, 850], fill=255)
    return m


def detalhes_porta_copos(img, cor):
    d = ImageDraw.Draw(img)
    escura = _misturar(_hex(cor), (0, 0, 0), 0.28)
    for r in (80, 150, 220):
        d.ellipse([450 - r, 570 - r, 450 + r, 570 + r], outline=escura, width=6)
    for i in range(24):
        a = i * math.pi / 12
        x, y = 450 + 270 * math.cos(a), 570 + 270 * math.sin(a)
        d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=_hex(cor))


def forma_cachecol():
    m = _mascara()
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([200, 200, 700, 380], radius=80, fill=255)
    d.rounded_rectangle([230, 300, 380, 960], radius=40, fill=255)
    d.rounded_rectangle([470, 300, 620, 880], radius=40, fill=255)
    return m


def detalhes_cachecol(img, cor):
    d = ImageDraw.Draw(img)
    escura = _misturar(_hex(cor), (0, 0, 0), 0.3)
    for x in range(240, 380, 18):
        d.line([x, 960, x - 4, 1040], fill=escura, width=8)
    for x in range(480, 620, 18):
        d.line([x, 880, x + 4, 960], fill=escura, width=8)


FORMAS = {
    "urso": (forma_urso, detalhes_urso),
    "coelho": (forma_coelho, detalhes_coelho),
    "polvo": (forma_polvo, detalhes_polvo),
    "baleia": (forma_baleia, detalhes_baleia),
    "estrela": (forma_estrela, detalhes_estrela),
    "cesto": (forma_cesto, detalhes_cesto),
    "bolsa": (forma_bolsa, detalhes_bolsa),
    "gorro": (forma_gorro, detalhes_gorro),
    "porta_copos": (forma_porta_copos, detalhes_porta_copos),
    "cachecol": (forma_cachecol, detalhes_cachecol),
}


def ilustrar(forma: str, cor: str, fundo: str | None = None, seed: int = 0, zoom=1.0) -> bytes:
    """Return a 900×1125 WebP of the piece in the given color."""
    fazer_mascara, detalhar = FORMAS[forma]
    rnd = random.Random(seed)
    fundo_rgb = _hex(fundo or rnd.choice(FUNDOS))
    img = Image.new("RGB", (LARGURA, ALTURA), fundo_rgb)

    # Background sparkles, like the little stars in the logo
    d = ImageDraw.Draw(img)
    tom = _misturar(fundo_rgb, (255, 255, 255), 0.5)
    for _ in range(7):
        x, y, r = rnd.randint(60, 840), rnd.randint(60, 1060), rnd.randint(8, 18)
        d.polygon([(x, y - r * 2), (x + r // 3, y), (x, y + r * 2), (x - r // 3, y)], fill=tom)
        d.polygon([(x - r * 2, y), (x, y - r // 3), (x + r * 2, y), (x, y + r // 3)], fill=tom)

    mascara = fazer_mascara()
    # Soft shadow
    sombra = mascara.filter(ImageFilter.GaussianBlur(28))
    sombra = ImageChops.offset(sombra, 14, 26).point(lambda p: int(p * 0.35))
    img.paste(_misturar(fundo_rgb, (0, 0, 0), 0.35), (0, 0), sombra)

    peca = textura_croche(cor, seed=seed)
    img.paste(peca, (0, 0), mascara)
    contorno = mascara.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.2))
    img.paste(_misturar(_hex(cor), (0, 0, 0), 0.45), (0, 0), contorno)
    detalhar(img, cor)

    if zoom != 1.0:
        w, h = int(LARGURA * zoom), int(ALTURA * zoom)
        img = img.resize((w, h), Image.LANCZOS)
        esquerda, topo = (w - LARGURA) // 2, (h - ALTURA) // 2
        img = img.crop((esquerda, topo, esquerda + LARGURA, topo + ALTURA))

    saida = io.BytesIO()
    img.save(saida, "WEBP", quality=80, method=5)
    return saida.getvalue()
