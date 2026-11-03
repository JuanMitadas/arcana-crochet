"""Peças da hospedagem na AWS: origem do CloudFront, fotos no S3, segredos no SSM."""

import os

import pytest
from django.test import Client, override_settings

from apps.core.middleware import OrigemCloudFrontMiddleware
from config.ssm import carregar_parametros

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"


@pytest.fixture
def via_cloudfront(settings):
    """Cliente com o segredo de origem ligado (o middleware lê o segredo ao ser criado)."""
    settings.ORIGEM_SEGREDO = SEGREDO
    return Client()


@pytest.mark.django_db
class TestOrigemCloudFront:
    def test_sem_segredo_configurado_nao_bloqueia(self, client):
        assert client.get("/sobre/").status_code == 200

    def test_pedido_direto_e_recusado(self, via_cloudfront):
        assert via_cloudfront.get("/sobre/").status_code == 403

    def test_pedido_com_segredo_errado_e_recusado(self, via_cloudfront):
        resposta = via_cloudfront.get("/sobre/", headers={"X-Arcana-Origem": "outro"})
        assert resposta.status_code == 403

    def test_pedido_do_cloudfront_passa(self, via_cloudfront):
        resposta = via_cloudfront.get("/sobre/", headers={"X-Arcana-Origem": SEGREDO})
        assert resposta.status_code == 200

    def test_healthz_fica_livre_para_o_aquecimento(self, via_cloudfront):
        assert via_cloudfront.get("/healthz/").status_code == 200
        # O Lambda Web Adapter entrega os eventos do EventBridge como POST.
        resposta = via_cloudfront.post("/healthz/", data="{}", content_type="application/json")
        assert resposta.json() == {"status": "ok"}

    def test_middleware_isolado(self, rf, settings):
        settings.ORIGEM_SEGREDO = SEGREDO
        middleware = OrigemCloudFrontMiddleware(lambda request: "ok")
        assert middleware(rf.get("/", HTTP_X_ARCANA_ORIGEM=SEGREDO)) == "ok"
        assert middleware(rf.get("/")).status_code == 403


@pytest.mark.django_db
def test_healthz_so_consulta_o_banco_quando_pedido(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        assert client.get("/healthz/").status_code == 200
    with django_assert_num_queries(1):
        assert client.get("/healthz/?banco=1").status_code == 200


@pytest.mark.django_db
def test_host_e_ip_vem_dos_cabecalhos_do_cloudfront(settings, client):
    settings.USE_X_FORWARDED_HOST = True
    settings.ALLOWED_HOSTS = ["*"]
    resposta = client.get(
        "/loja/", headers={"X-Forwarded-Host": "arcanacrochet.com.br"}, secure=False
    )
    assert resposta.wsgi_request.get_host() == "arcanacrochet.com.br"

    from allauth.core.internal.httpkit import get_client_ip

    settings.ALLAUTH_TRUSTED_CLIENT_IP_HEADER = "X-Arcana-Ip"
    pedido = client.get("/", headers={"X-Arcana-Ip": "203.0.113.9"}).wsgi_request
    assert get_client_ip(pedido) == "203.0.113.9"


@override_settings(MEDIA_URL="/media/")
def test_fotos_no_s3_tem_url_relativa_servida_pelo_cloudfront():
    from apps.core.storage import MidiaS3

    storage = MidiaS3(bucket_name="arcana-midia", location="media", region_name="sa-east-1")
    assert storage.url("produtos/abc/1 foto.webp") == "/media/produtos/abc/1%20foto.webp"
    # No bucket, o arquivo fica sob media/, que é o caminho liberado para o CloudFront.
    assert storage._normalize_name("produtos/abc/1.webp") == "media/produtos/abc/1.webp"


class SsmFalso:
    """Imita o paginador do boto3 para get_parameters_by_path."""

    def __init__(self, parametros):
        self.parametros = parametros
        self.pedidos = []

    def get_paginator(self, nome):
        assert nome == "get_parameters_by_path"
        return self

    def paginate(self, **kwargs):
        self.pedidos.append(kwargs)
        yield {"Parameters": self.parametros[:1]}
        yield {"Parameters": self.parametros[1:]}


def test_ssm_carrega_parametros_sem_sobrescrever_o_ambiente(monkeypatch):
    monkeypatch.setenv("ARCANA_TESTE_DEFINIDA", "do-ambiente")
    monkeypatch.delenv("ARCANA_TESTE_SEGREDO", raising=False)
    cliente = SsmFalso(
        [
            {"Name": "/arcana/prod/ARCANA_TESTE_SEGREDO", "Value": "s3cr3t"},
            {"Name": "/arcana/prod/ARCANA_TESTE_DEFINIDA", "Value": "do-ssm"},
        ]
    )
    try:
        carregados = carregar_parametros("arcana/prod", cliente=cliente)
        assert carregados == ["ARCANA_TESTE_SEGREDO"]
        assert os.environ["ARCANA_TESTE_SEGREDO"] == "s3cr3t"
        assert os.environ["ARCANA_TESTE_DEFINIDA"] == "do-ambiente"
        assert cliente.pedidos == [
            {"Path": "/arcana/prod/", "Recursive": False, "WithDecryption": True}
        ]
    finally:
        os.environ.pop("ARCANA_TESTE_SEGREDO", None)


def test_ssm_sem_prefixo_nao_faz_nada():
    assert carregar_parametros("") == []
