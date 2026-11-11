from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline

from apps.core.templatetags.dinheiro import brl

from . import servicos
from .models import Cupom, Pedido, PedidoItem


class ItemInline(TabularInline):
    model = PedidoItem
    extra = 0
    can_delete = False
    fields = ["nome", "detalhes", "sku", "quantidade", "preco", "sob_encomenda"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="preço unitário")
    def preco(self, obj):
        return brl(obj.preco_unitario_centavos)


@admin.register(Pedido)
class PedidoAdmin(ModelAdmin):
    list_display = [
        "codigo", "cliente", "status", "total", "metodo_pagamento", "pagar_ate", "criado_em"
    ]  # fmt: skip
    list_filter = ["status", "metodo_pagamento"]
    search_fields = ["codigo", "cliente__email", "codigo_rastreio"]
    date_hierarchy = "criado_em"
    inlines = [ItemInline]
    actions = ["aprovar_pagamento", "avancar_status", "cancelar"]
    readonly_fields = [
        "codigo", "cliente", "status", "metodo_pagamento", "parcelas", "subtotal_centavos",
        "desconto_cupom_centavos", "desconto_pix_centavos", "frete_centavos", "total_centavos",
        "cupom", "endereco_entrega", "frete_servico", "frete_prazo_dias", "observacao",
        "pago_em", "separado_em", "enviado_em", "entregue_em", "cancelado_em", "criado_em",
    ]  # fmt: skip
    fieldsets = [
        (None, {"fields": ["codigo", "cliente", "status", "criado_em", "observacao"]}),
        (
            "Valores",
            {
                "fields": [
                    "metodo_pagamento",
                    "parcelas",
                    "subtotal_centavos",
                    "cupom",
                    "desconto_cupom_centavos",
                    "desconto_pix_centavos",
                    "frete_centavos",
                    "total_centavos",
                ]  # fmt: skip
            },
        ),
        (
            "Entrega",
            {
                "fields": [
                    "endereco_entrega",
                    "frete_servico",
                    "frete_prazo_dias",
                    "transportadora",
                    "codigo_rastreio",
                    "url_rastreio",
                ]  # fmt: skip
            },
        ),
        (
            "Linha do tempo",
            {"fields": ["pago_em", "separado_em", "enviado_em", "entregue_em", "cancelado_em"]},
        ),
    ]

    def has_add_permission(self, request):
        return False

    @admin.display(description="pagar até")
    def pagar_ate(self, obj):
        # Pix lands in the bank account without telling the site: compare with the bank
        # app and use "Aprovar pagamento (manual)". Overdue orders are cancelled hourly.
        if obj.status != Pedido.Status.AGUARDANDO_PAGAMENTO:
            return "—"
        return timezone.localtime(obj.pagar_ate).strftime("%d/%m %H:%M")

    @admin.display(description="total", ordering="total_centavos")
    def total(self, obj):
        return brl(obj.total_centavos)

    def _aplicar(self, request, queryset, funcao, sucesso):
        feitos = 0
        for pedido in queryset:
            try:
                funcao(pedido)
                feitos += 1
            except ValidationError as erro:
                self.message_user(request, f"{pedido}: {erro.messages[0]}", messages.WARNING)
        if feitos:
            self.message_user(request, f"{feitos} pedido(s) {sucesso}.")

    @admin.action(description="Aprovar pagamento (manual)")
    def aprovar_pagamento(self, request, queryset):
        self._aplicar(request, queryset, servicos.marcar_pago, "marcado(s) como pagos")

    @admin.action(description="Avançar para a próxima etapa")
    def avancar_status(self, request, queryset):
        self._aplicar(request, queryset, servicos.avancar, "avançado(s)")

    @admin.action(description="Cancelar e devolver ao estoque")
    def cancelar(self, request, queryset):
        self._aplicar(request, queryset, servicos.cancelar, "cancelado(s)")


@admin.register(Cupom)
class CupomAdmin(ModelAdmin):
    list_display = ["codigo", "tipo", "valor", "minimo_centavos", "usos", "limite_usos", "ativo"]
    list_filter = ["tipo", "ativo"]
    search_fields = ["codigo"]
    readonly_fields = ["usos"]
