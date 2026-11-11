from unfold.forms import AdminPasswordChangeForm as SenhaAdminForm  # noqa: F401 (used by the admin)
from unfold.forms import UserChangeForm, UserCreationForm

from .models import Usuario


class UsuarioCriacaoForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "papel")


class UsuarioAlteracaoForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"
