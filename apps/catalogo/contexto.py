from django.db.models import Prefetch

from .models import Categoria


def menu_categorias(request):
    """Categorias do menu principal com subcategorias. O queryset é preguiçoso:
    só consulta o banco nas páginas que de fato desenham o menu."""
    filhas = Prefetch("filhas", queryset=Categoria.objects.filter(ativa=True))
    menu = Categoria.objects.filter(ativa=True, pai__isnull=True).prefetch_related(filhas)
    return {"menu_categorias": menu}
