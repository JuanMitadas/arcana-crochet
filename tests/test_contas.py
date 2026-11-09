import pytest
from django.contrib.auth.models import Group
from django.core import mail

from apps.contas.models import Usuario


@pytest.mark.django_db
class TestUsuario:
    def test_cliente_nao_acessa_o_painel(self):
        usuario = Usuario.objects.create_user("Maria@Exemplo.com", "senha-forte-123")
        assert usuario.email == "maria@exemplo.com"
        assert usuario.papel == Usuario.Papel.CLIENTE
        assert not usuario.is_staff

    def test_atendente_acessa_o_painel(self):
        usuario = Usuario.objects.create_user(
            "ana@arcana.test", "senha-forte-123", papel=Usuario.Papel.ATENDENTE
        )
        assert usuario.is_staff
        assert not usuario.is_superuser

    def test_superusuario_e_admin(self, admin_usuario):
        assert admin_usuario.papel == Usuario.Papel.ADMIN
        assert admin_usuario.is_staff
        assert admin_usuario.is_superuser

    def test_rebaixar_papel_remove_acesso_ao_painel(self):
        usuario = Usuario.objects.create_user(
            "ana@arcana.test", "senha-forte-123", papel=Usuario.Papel.ATENDENTE
        )
        usuario.papel = Usuario.Papel.CLIENTE
        usuario.save()
        assert not usuario.is_staff

    def test_grupo_atendimento_existe_com_permissoes(self):
        grupo = Group.objects.get(name="Atendimento")
        codigos = set(grupo.permissions.values_list("codename", flat=True))
        assert {"view_produto", "add_movimentacaoestoque"} <= codigos
        assert "delete_produto" not in codigos


@pytest.mark.django_db
class TestCadastroELogin:
    @pytest.mark.parametrize("url", ["/conta/login/", "/conta/signup/", "/conta/password/reset/"])
    def test_telas_de_conta_usam_o_layout_da_loja(self, client, url):
        resposta = client.get(url)
        assert resposta.status_code == 200
        assert "Arcana Crochet" in resposta.content.decode()

    def test_cadastro_envia_email_de_verificacao(self, client):
        resposta = client.post(
            "/conta/signup/",
            {
                "email": "nova@cliente.com",
                "password1": "uma-senha-bem-forte-42",
                "password2": "uma-senha-bem-forte-42",
            },
        )
        assert resposta.status_code == 302
        assert Usuario.objects.filter(email="nova@cliente.com").exists()
        assert len(mail.outbox) == 1
        assert "nova@cliente.com" in mail.outbox[0].to

    def test_senha_curta_e_recusada(self, client):
        client.post(
            "/conta/signup/",
            {"email": "curta@cliente.com", "password1": "abc12345", "password2": "abc12345"},
        )
        assert not Usuario.objects.filter(email="curta@cliente.com").exists()

    def test_login_sem_email_verificado_nao_entra(self, client):
        Usuario.objects.create_user("sem@verificar.com", "uma-senha-bem-forte-42")
        client.post(
            "/conta/login/", {"login": "sem@verificar.com", "password": "uma-senha-bem-forte-42"}
        )
        assert "_auth_user_id" not in client.session
