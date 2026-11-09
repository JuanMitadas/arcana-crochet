from django.conf import settings


def loja(request):
    """Store rules available in every template (announcement bar, footer)."""
    return {"loja": settings.LOJA}
