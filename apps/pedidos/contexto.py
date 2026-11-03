from .carrinho import CHAVE


def sacola(request):
    """Quantidade de itens da sacola para o ícone do cabeçalho (sem consultar o banco)."""
    sessao = getattr(request, "session", None)
    dados = (sessao.get(CHAVE) if sessao is not None else None) or {}
    return {"sacola_quantidade": sum((dados.get("itens") or {}).values())}
