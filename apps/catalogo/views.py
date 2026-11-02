from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView

from .models import Categoria, Produto, ProdutoFoto, ProdutoVariacao


def _com_fotos(queryset):
    return queryset.select_related("categoria").prefetch_related(
        Prefetch("fotos", queryset=ProdutoFoto.objects.order_by("ordem")),
        Prefetch("variacoes", queryset=ProdutoVariacao.objects.filter(ativa=True)),
    )


class VitrineView(ListView):
    template_name = "catalogo/vitrine.html"
    context_object_name = "produtos"
    paginate_by = 24

    def get_queryset(self):
        produtos = _com_fotos(Produto.objects.visiveis())
        self.categoria = None
        slug = self.request.GET.get("categoria")
        if slug:
            self.categoria = get_object_or_404(Categoria, slug=slug, ativa=True)
            produtos = produtos.filter(categoria__in=[self.categoria, *self.categoria.filhas.all()])
        return produtos.order_by("-destaque", "-publicado_em", "-criado_em")

    def get_template_names(self):
        # Com HTMX, devolve só a grade para trocar o conteúdo sem recarregar a página.
        if self.request.htmx:
            return ["catalogo/vitrine.html#grade"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["categorias"] = Categoria.objects.filter(ativa=True, pai__isnull=True)
        contexto["categoria_atual"] = self.categoria
        return contexto


def produto_detalhe(request, slug):
    produto = get_object_or_404(_com_fotos(Produto.objects.visiveis()), slug=slug)
    return render(request, "catalogo/produto.html", {"produto": produto})
