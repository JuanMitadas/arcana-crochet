from django.contrib import admin

from .models import Avaliacao


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ["produto", "nota", "titulo", "autor", "status", "criado_em"]
    list_filter = ["status", "nota"]
    search_fields = ["produto__nome", "titulo", "comentario", "autor__email"]
    readonly_fields = ["produto", "item", "autor", "nota", "titulo", "comentario", "criado_em"]
    fields = [*readonly_fields, "status", "resposta_loja"]
    actions = ["publicar", "ocultar"]

    def has_add_permission(self, request):
        return False  # avaliações nascem de compras entregues

    @admin.action(description="Publicar avaliações selecionadas")
    def publicar(self, request, queryset):
        total = queryset.update(status=Avaliacao.Status.PUBLICADA)
        self.message_user(request, f"{total} avaliação(ões) publicada(s).")

    @admin.action(description="Ocultar avaliações selecionadas")
    def ocultar(self, request, queryset):
        total = queryset.update(status=Avaliacao.Status.OCULTA)
        self.message_user(request, f"{total} avaliação(ões) oculta(s).")
