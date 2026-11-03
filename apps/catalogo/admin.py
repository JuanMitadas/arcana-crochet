from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.templatetags.dinheiro import brl

from .estoque import registrar_movimentacao
from .models import (
    Categoria,
    MovimentacaoEstoque,
    Produto,
    ProdutoEspecificacao,
    ProdutoFoto,
    ProdutoVariacao,
)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "ordem", "ativa"]
    fields = ["nome", "slug", "pai", "descricao", "imagem", "ordem", "ativa"]
    list_editable = ["ordem", "ativa"]
    prepopulated_fields = {"slug": ["nome"]}
    search_fields = ["nome"]


class VariacaoInline(admin.TabularInline):
    model = ProdutoVariacao
    extra = 1
    fields = ["sku", "cor", "cor_hex", "tamanho", "preco_ajuste_centavos", "estoque", "ativa"]
    readonly_fields = ["estoque"]


class FotoInline(admin.TabularInline):
    model = ProdutoFoto
    extra = 1
    fields = ["imagem", "texto_alternativo", "variacao", "ordem"]


class EspecificacaoInline(admin.TabularInline):
    model = ProdutoEspecificacao
    extra = 2
    fields = ["nome", "valor", "ordem"]


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "preco", "status", "destaque", "disponibilidade"]
    list_filter = ["status", "categoria", "disponibilidade", "destaque"]
    search_fields = ["nome", "descricao", "variacoes__sku"]
    prepopulated_fields = {"slug": ["nome"]}
    inlines = [VariacaoInline, FotoInline, EspecificacaoInline]
    actions = ["publicar", "pausar"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "nome",
                    "slug",
                    "categoria",
                    "descricao",
                    "material",
                    "cuidados",
                    "video",
                    "status",
                ]
            },
        ),
        (
            "Preço",
            {"fields": ["preco_centavos", "preco_promocional_centavos", "custo_centavos"]},
        ),
        (
            "Disponibilidade",
            {"fields": ["disponibilidade", "prazo_producao_dias", "personalizavel", "destaque"]},
        ),
        (
            "Embalagem (usada no cálculo de frete)",
            {"fields": ["peso_g", "altura_cm", "largura_cm", "comprimento_cm"]},
        ),
        ("Publicação", {"fields": ["publicado_em"]}),
    ]

    @admin.display(description="preço", ordering="preco_centavos")
    def preco(self, obj):
        return brl(obj.preco_atual_centavos)

    @admin.action(description="Publicar produtos selecionados")
    def publicar(self, request, queryset):
        total = queryset.update(status=Produto.Status.ATIVO, publicado_em=timezone.now())
        self.message_user(request, f"{total} produto(s) publicado(s).")

    @admin.action(description="Pausar produtos selecionados")
    def pausar(self, request, queryset):
        total = queryset.update(status=Produto.Status.PAUSADO)
        self.message_user(request, f"{total} produto(s) pausado(s).")


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ["variacao", "tipo", "quantidade", "motivo"]

    def clean(self):
        dados = super().clean()
        variacao, quantidade = dados.get("variacao"), dados.get("quantidade")
        if variacao and quantidade is not None:
            if quantidade == 0:
                self.add_error("quantidade", "A quantidade não pode ser zero.")
            elif variacao.estoque + quantidade < variacao.estoque_reservado:
                self.add_error(
                    "quantidade",
                    f"Estoque insuficiente: há {variacao.disponivel} unidade(s) disponível(is).",
                )
        return dados


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    """Registrar uma movimentação aqui é a forma de alterar o estoque pelo painel."""

    form = MovimentacaoForm
    list_display = ["criado_em", "variacao", "tipo", "quantidade", "estoque_resultante", "autor"]
    list_filter = ["tipo"]
    search_fields = ["variacao__sku", "variacao__produto__nome", "motivo"]
    autocomplete_fields = ["variacao"]

    def has_change_permission(self, request, obj=None):
        return False  # o histórico é imutável

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            nova = registrar_movimentacao(
                obj.variacao, obj.tipo, obj.quantidade, autor=request.user, motivo=obj.motivo
            )
        except ValidationError as erro:
            # Só acontece se outra operação mudou o estoque entre a validação e o salvamento.
            self.message_user(request, erro.messages[0], level=messages.ERROR)
            raise
        obj.pk = nova.pk
        obj.estoque_resultante = nova.estoque_resultante


@admin.register(ProdutoVariacao)
class ProdutoVariacaoAdmin(admin.ModelAdmin):
    list_display = ["sku", "produto", "cor", "tamanho", "estoque", "estoque_reservado", "ativa"]
    list_filter = ["ativa"]
    search_fields = ["sku", "produto__nome", "cor"]
    readonly_fields = ["estoque", "estoque_reservado"]
