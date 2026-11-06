from django import template

register = template.Library()


@register.filter
def brl(centavos):
    """Format cents as Brazilian currency: 123456 -> "R$ 1.234,56"."""
    if centavos is None or centavos == "":
        return ""
    centavos = int(centavos)
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{resto:02d}"
