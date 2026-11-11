"""django-allauth customizations for the store's accounts."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AdaptadorSocial(DefaultSocialAccountAdapter):
    """Accounts created with "Continuar com o Google"."""

    def populate_user(self, request, sociallogin, data):
        # The user model has no first/last name: keep Google's full name instead.
        usuario = super().populate_user(request, sociallogin, data)
        nome = data.get("name") or " ".join(
            filter(None, [data.get("first_name"), data.get("last_name")])
        )
        if nome and not usuario.nome_completo:
            usuario.nome_completo = nome.strip()[:150]
        return usuario
