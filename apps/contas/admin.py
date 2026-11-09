from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import UsuarioAlteracaoForm, UsuarioCriacaoForm
from .models import Endereco, Usuario


class EnderecoInline(admin.StackedInline):
    model = Endereco
    extra = 0


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [EnderecoInline]
    form = UsuarioAlteracaoForm
    add_form = UsuarioCriacaoForm
    ordering = ["-date_joined"]
    list_display = ["email", "nome_completo", "papel", "is_active", "date_joined", "last_login"]
    list_filter = ["papel", "is_active"]
    search_fields = ["email", "nome_completo", "nome_exibicao"]
    readonly_fields = ["date_joined", "last_login", "termos_versao", "termos_aceitos_em"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Dados pessoais", {"fields": ["nome_completo", "nome_exibicao"]}),
        ("Acesso", {"fields": ["papel", "is_active", "is_superuser", "groups"]}),
        ("Equipe", {"fields": ["observacao_interna"]}),
        (
            "Registro",
            {"fields": ["date_joined", "last_login", "termos_versao", "termos_aceitos_em"]},
        ),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "papel", "password1", "password2"]}),
    ]
    filter_horizontal = ["groups"]
