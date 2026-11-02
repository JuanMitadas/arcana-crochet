from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Usuario


class UsuarioCriacaoForm(BaseUserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "papel")


class UsuarioAlteracaoForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"
