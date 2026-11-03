from django.conf import settings


def loja(request):
    """Regras comerciais disponíveis em todos os templates (faixa de avisos, rodapé)."""
    return {"loja": settings.LOJA}
