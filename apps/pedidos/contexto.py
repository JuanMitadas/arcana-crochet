from .carrinho import CHAVE


def sacola(request):
    """Number of items in the bag for the header icon (without querying the database)."""
    sessao = getattr(request, "session", None)
    dados = (sessao.get(CHAVE) if sessao is not None else None) or {}
    return {"sacola_quantidade": sum((dados.get("itens") or {}).values())}
