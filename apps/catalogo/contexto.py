from django.db.models import Prefetch

from .models import Categoria


def menu_categorias(request):
    """Main menu categories with their subcategories. The queryset is lazy: it only
    hits the database on pages that actually render the menu."""
    filhas = Prefetch("filhas", queryset=Categoria.objects.filter(ativa=True))
    menu = Categoria.objects.filter(ativa=True, pai__isnull=True).prefetch_related(filhas)
    return {"menu_categorias": menu}
