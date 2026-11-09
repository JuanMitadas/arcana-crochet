from django import template

from apps.core import precos

from .dinheiro import brl

register = template.Library()


@register.filter
def pix(centavos):
    """Formatted Pix price: {{ produto.preco_atual_centavos|pix }}"""
    if centavos in (None, ""):
        return ""
    return brl(precos.preco_pix(int(centavos)))


@register.filter
def parcelas(centavos):
    """Installment text: "3x de R$ 43,30 sem juros"."""
    if centavos in (None, ""):
        return ""
    p = precos.parcelamento(int(centavos))
    if p.vezes == 1:
        return "à vista no cartão"
    return f"{p.vezes}x de {brl(p.valor_parcela_centavos)} sem juros"


@register.filter
def desconto_pct(produto):
    return precos.percentual_desconto(produto.preco_centavos, produto.preco_promocional_centavos)


@register.inclusion_tag("componentes/estrelas.html")
def estrelas(nota, tamanho="sm", total=None):
    """Show the rating (0 to 5) as full, half and empty stars."""
    nota = float(nota or 0)
    meias = round(nota * 2)
    cheias, meia = divmod(meias, 2)
    return {
        "cheias": range(cheias),
        "meia": bool(meia),
        "vazias": range(5 - cheias - meia),
        "nota": nota,
        "total": total,
        "tamanho": tamanho,
    }


@register.simple_tag(takes_context=True)
def url_com(context, **mudancas):
    """Keep the current URL's filters, changing only some parameters."""
    params = context["request"].GET.copy()
    for chave, valor in mudancas.items():
        if valor in (None, ""):
            params.pop(chave, None)
        else:
            params[chave] = valor
    if "page" not in mudancas:
        params.pop("page", None)
    texto = params.urlencode()
    return f"?{texto}" if texto else "?"


@register.filter
def primeiro_nome(nome):
    return (nome or "").split(" ")[0][:16]


@register.filter
def cep(valor):
    valor = "".join(c for c in str(valor or "") if c.isdigit())
    return f"{valor[:5]}-{valor[5:]}" if len(valor) == 8 else valor


@register.filter
def telefone(valor):
    n = "".join(c for c in str(valor or "") if c.isdigit())
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return valor


@register.filter
def foto_principal(produto):
    """First photo (uses the prefetch, no extra query)."""
    fotos = list(produto.fotos.all())
    return fotos[0] if fotos else None


@register.filter
def foto_secundaria(produto):
    fotos = list(produto.fotos.all())
    return fotos[1] if len(fotos) > 1 else None


@register.filter
def porcentagem(parte, total):
    try:
        return round(int(parte) * 100 / int(total)) if int(total) else 0
    except (TypeError, ValueError):
        return 0
