"""Pix straight to the store's account and cancellation of unpaid orders."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.pedidos import pix, servicos
from apps.pedidos.carrinho import Carrinho
from apps.pedidos.models import Pedido
from tests.conftest import Requisicao
from tests.test_pedidos import _fechar

PIX = {
    "PIX_CHAVE": "loja@arcana.test",
    "PIX_RECEBEDOR": "Kamilly Araújo",
    "PIX_CIDADE": "São Paulo",
}


@pytest.fixture
def com_pix(settings):
    settings.LOJA = {**settings.LOJA, **PIX}


def _campos(texto: str) -> dict:
    """Split a BR Code into {id: value} (top level only)."""
    campos, i = {}, 0
    while i < len(texto):
        identificador, tamanho = texto[i : i + 2], int(texto[i + 2 : i + 4])
        campos[identificador] = texto[i + 4 : i + 4 + tamanho]
        i += 4 + tamanho
    return campos


class TestBrCode:
    def test_crc_do_exemplo_do_banco_central(self):
        # Example from the BR Code manual (Manual de Padrões para Iniciação do Pix).
        exemplo = (
            "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
            "5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***6304"
        )
        assert pix.crc16(exemplo) == "1D3D"

    def test_campos_do_copia_e_cola(self):
        texto = pix.copia_e_cola(
            "loja@arcana.test", "Kamilly Araújo", "São Paulo", 12345, "ARC-AB23"
        )
        campos = _campos(texto)
        assert campos["00"] == "01"
        assert campos["26"] == "0014br.gov.bcb.pix0116loja@arcana.test"
        assert campos["53"] == "986" and campos["54"] == "123.45" and campos["58"] == "BR"
        assert campos["59"] == "KAMILLY ARAUJO" and campos["60"] == "SAO PAULO"
        assert campos["62"] == "0507ARCAB23"
        assert campos["63"] == pix.crc16(texto[:-4])

    def test_nome_e_cidade_sao_cortados_no_limite(self):
        texto = pix.copia_e_cola("x@y.z", "A" * 40, "Santana de Parnaíba", 100, "ARC-1")
        campos = _campos(texto)
        assert len(campos["59"]) == 25 and campos["60"] == "SANTANA DE PARN"


@pytest.mark.django_db
class TestPaginaDoPedido:
    def test_mostra_qr_code_e_copia_e_cola(
        self, client, cliente, endereco, carrinho, pronta, com_pix
    ):
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho, metodo="pix")
        client.force_login(cliente)
        html = client.get(pedido.get_absolute_url()).content.decode()
        assert 'class="w-full h-auto"><g transform="scale(4)">' in html
        assert pix.cobranca(pedido)["copia_e_cola"] in html
        assert "Pague até" in html

    def test_sem_chave_configurada_pede_contato(self, client, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho, metodo="pix")
        client.force_login(cliente)
        html = client.get(pedido.get_absolute_url()).content.decode()
        assert "O código Pix não está disponível agora" in html

    def test_pedido_pago_nao_mostra_pix(self, client, cliente, endereco, carrinho, pronta, com_pix):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho, metodo="pix"))
        client.force_login(cliente)
        assert "pix-copia-cola" not in client.get(pedido.get_absolute_url()).content.decode()


@pytest.mark.django_db
class TestPedidosVencidos:
    def _vencer(self, pedido, horas=25):
        Pedido.objects.filter(pk=pedido.pk).update(
            criado_em=timezone.now() - timedelta(hours=horas)
        )

    def test_cancela_so_os_vencidos_e_devolve_as_pecas(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        vencido = _fechar(cliente, endereco, carrinho)
        outra_sacola = Carrinho(Requisicao())
        outra_sacola.adicionar(pronta, 1)
        recente = _fechar(cliente, endereco, outra_sacola)
        self._vencer(vencido)

        assert servicos.cancelar_vencidos() == 1
        vencido.refresh_from_db()
        recente.refresh_from_db()
        pronta.refresh_from_db()
        assert vencido.status == Pedido.Status.CANCELADO
        assert recente.status == Pedido.Status.AGUARDANDO_PAGAMENTO
        assert pronta.estoque_reservado == 1

    def test_pedido_pago_nunca_e_cancelado(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        self._vencer(pedido, horas=100)
        assert servicos.cancelar_vencidos() == 0
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.PAGO

    def test_prazo_configuravel(self, settings, cliente, endereco, carrinho, pronta):
        settings.LOJA = {**settings.LOJA, "PRAZO_PAGAMENTO_HORAS": 48}
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho)
        self._vencer(pedido, horas=25)
        assert servicos.cancelar_vencidos() == 0
        assert pedido.pagar_ate == pedido.criado_em + timedelta(hours=48)

    def test_tarefa_agendada_pelo_healthz(self, client, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        self._vencer(_fechar(cliente, endereco, carrinho))
        evento = json.dumps({"tarefa": "cancelar_pedidos_vencidos"})
        resposta = client.post("/healthz/", data=evento, content_type="application/json")
        assert resposta.json() == {"status": "ok", "cancelados": 1}
        # The warm-up ping still answers without touching orders.
        aquecimento = client.post(
            "/healthz/", data='{"aquecimento": true}', content_type="application/json"
        )
        assert aquecimento.json() == {"status": "ok"}

    def test_comando(self, cliente, endereco, carrinho, pronta):
        from io import StringIO

        from django.core.management import call_command

        carrinho.adicionar(pronta, 1)
        self._vencer(_fechar(cliente, endereco, carrinho))
        saida = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=saida)
        assert "Cancelled orders: 1" in saida.getvalue()
