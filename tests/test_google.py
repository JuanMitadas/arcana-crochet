"""Sign in with Google (django-allauth)."""

import pytest
from allauth.socialaccount.models import SocialLogin
from django.test import RequestFactory

from apps.contas.adaptadores import AdaptadorSocial
from apps.contas.models import Usuario

GOOGLE = {
    "google": {
        "APPS": [{"client_id": "teste.apps.googleusercontent.com", "secret": "segredo"}],
        "SCOPE": ["openid", "email", "profile"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
    }
}


@pytest.fixture
def com_google(settings):
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE


@pytest.mark.django_db
class TestBotao:
    def test_sem_credenciais_nao_aparece(self, client):
        assert "Continuar com o Google" not in client.get("/conta/login/").content.decode()

    @pytest.mark.parametrize("url", ["/conta/login/", "/conta/signup/"])
    def test_aparece_no_login_e_no_cadastro(self, client, com_google, url):
        html = client.get(url).content.decode()
        assert "Continuar com o Google" in html
        assert 'action="/conta/google/login/?process=login"' in html

    def test_aparece_no_checkout(self, client, com_google, pronta):
        client.post("/sacola/adicionar/", {"variacao": str(pronta.pk), "quantidade": 1})
        html = client.get("/checkout/identificacao/").content.decode()
        assert "Continuar com o Google" in html

    def test_botao_leva_ao_google(self, client, com_google):
        resposta = client.post("/conta/google/login/?process=login")
        assert resposta.status_code == 302
        assert resposta.url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=teste.apps.googleusercontent.com" in resposta.url


def test_csp_deixa_o_formulario_ir_para_o_google(settings):
    assert "https://accounts.google.com" in settings.SECURE_CSP["form-action"]


def test_conta_nova_recebe_o_nome_do_google(settings):
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE
    request = RequestFactory().get("/")
    sociallogin = SocialLogin(user=Usuario())
    usuario = AdaptadorSocial().populate_user(
        request, sociallogin, {"email": "ana@gmail.com", "name": "Ana Souza"}
    )
    assert usuario.email == "ana@gmail.com" and usuario.nome_completo == "Ana Souza"
