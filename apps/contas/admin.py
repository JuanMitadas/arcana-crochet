from allauth.account.admin import EmailAddressAdmin as BaseEmailAddressAdmin
from allauth.account.models import EmailAddress
from allauth.mfa.admin import AuthenticatorAdmin as BaseAuthenticatorAdmin
from allauth.mfa.models import Authenticator
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin, StackedInline

from .forms import SenhaAdminForm, UsuarioAlteracaoForm, UsuarioCriacaoForm
from .models import Endereco, Usuario

# Models registered by Django and allauth, again with the admin theme.
admin.site.unregister(Group)
admin.site.unregister(EmailAddress)
admin.site.unregister(Authenticator)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


@admin.register(EmailAddress)
class EmailAddressAdmin(BaseEmailAddressAdmin, ModelAdmin):
    pass


@admin.register(Authenticator)
class AuthenticatorAdmin(BaseAuthenticatorAdmin, ModelAdmin):
    pass


class EnderecoInline(StackedInline):
    model = Endereco
    extra = 0


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    inlines = [EnderecoInline]
    form = UsuarioAlteracaoForm
    add_form = UsuarioCriacaoForm
    change_password_form = SenhaAdminForm
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
