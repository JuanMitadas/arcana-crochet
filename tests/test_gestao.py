"""Management panel (/gestao/): access, orders, pieces, stock, photos and reviews."""

import io

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.avaliacoes.models import Avaliacao
from apps.catalogo.models import Produto, ProdutoFoto
from apps.contas.models import Usuario
from apps.gestao.forms import CampoReais
from apps.pedidos import servicos
from apps.pedidos.models import Pedido
from tests.test_pedidos import _fechar


@pytest.fixture
def equipe(client, admin_usuario):
    client.force_login(admin_usuario)
    return client


@pytest.fixture
def pedido(cliente, endereco, carrinho, pronta):
    carrinho.adicionar(pronta, 1)
    return _fechar(cliente, endereco, carrinho)


def _foto(nome="foto.png"):
    arquivo = io.BytesIO()
    Image.new("RGB", (40, 40), "#17597c").save(arquivo, "PNG")
    return SimpleUploadedFile(nome, arquivo.getvalue(), content_type="image/png")


@pytest.mark.django_db
class TestAcesso:
    def test_visitante_vai_para_o_login(self, client):
        resposta = client.get("/gestao/")
        assert resposta.status_code == 302 and "/conta/login/" in resposta.url

    def test_cliente_nao_entra(self, client, cliente):
        client.force_login(cliente)
        assert client.get("/gestao/").status_code == 403

    def test_equipe_ve_todas_as_paginas(self, equipe, pedido, produto):
        for url in [
            "/gestao/",
            "/gestao/pedidos/",
            "/gestao/pedidos/?etapa=todos",
            f"/gestao/pedidos/{pedido.codigo}/",
            "/gestao/pecas/",
            "/gestao/pecas/nova/",
            f"/gestao/pecas/{produto.pk}/",
            "/gestao/avaliacoes/",
        ]:
            assert equipe.get(url).status_code == 200, url

    def test_atendente_ve_so_o_que_o_grupo_permite(self, client, produto):
        atendente = Usuario.objects.create_user("atende@arcana.test", "senha-123-forte")
        atendente.papel = Usuario.Papel.ATENDENTE
        atendente.save()
        atendente.groups.add(Group.objects.get(name="Atendimento"))
        client.force_login(atendente)
        assert client.get("/gestao/pecas/").status_code == 200
        assert client.get("/gestao/pedidos/").status_code == 403
        html = client.get(f"/gestao/pecas/{produto.pk}/").content.decode()
        assert "Salvar peça" not in html
        assert client.post(f"/gestao/pecas/{produto.pk}/", {}).status_code == 403

    def test_loja_mostra_atalho_so_para_a_equipe(self, client, cliente, admin_usuario):
        client.force_login(cliente)
        assert "/gestao/" not in client.get("/").content.decode()
        client.force_login(admin_usuario)
        assert "/gestao/" in client.get("/").content.decode()


@pytest.mark.django_db
class TestPedidos:
    def test_confirmar_pix_separar_enviar_entregar(self, equipe, pedido):
        base = f"/gestao/pedidos/{pedido.codigo}"
        equipe.post(f"{base}/confirmar-pix/")
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.PAGO

        equipe.post(f"{base}/separar/")
        resposta = equipe.post(f"{base}/enviar/", {"codigo_rastreio": ""}, follow=True)
        assert "Informe o código de rastreio" in resposta.content.decode()
        equipe.post(f"{base}/enviar/", {"codigo_rastreio": "aa123456789br"})
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.ENVIADO and pedido.codigo_rastreio == "AA123456789BR"

        equipe.post(f"{base}/entregar/")
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.ENTREGUE

    def test_botao_antigo_nao_pula_etapa(self, equipe, pedido):
        # "Marcar como entregue" from a stale page must not move a paid order.
        servicos.marcar_pago(pedido)
        resposta = equipe.post(f"/gestao/pedidos/{pedido.codigo}/entregar/", follow=True)
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.PAGO
        assert "mudou de etapa" in resposta.content.decode()

    def test_cancelar_devolve_as_pecas(self, equipe, pedido, pronta):
        equipe.post(f"/gestao/pedidos/{pedido.codigo}/cancelar/", {"motivo": "duplicado"})
        pedido.refresh_from_db()
        pronta.refresh_from_db()
        assert pedido.status == Pedido.Status.CANCELADO
        assert pronta.estoque_reservado == 0

    def test_volta_para_a_lista_de_onde_veio(self, equipe, pedido):
        resposta = equipe.post(
            f"/gestao/pedidos/{pedido.codigo}/confirmar-pix/",
            {"voltar": "/gestao/pedidos/?etapa=pagar"},
        )
        assert resposta.url == "/gestao/pedidos/?etapa=pagar"
        resposta = equipe.post(
            f"/gestao/pedidos/{pedido.codigo}/separar/", {"voltar": "https://exemplo.com/"}
        )
        assert resposta.url == f"/gestao/pedidos/{pedido.codigo}/"

    def test_inicio_lista_pix_pendente(self, equipe, pedido):
        html = equipe.get("/gestao/").content.decode()
        assert pedido.codigo in html and "Pix recebido: confirmar" in html


class TestCampoReais:
    @pytest.mark.parametrize(
        ("texto", "centavos"),
        [("129,90", 12990), ("1.299,90", 129990), ("129", 12900), ("R$ 9,5", 950), ("", None)],
    )
    def test_converte(self, texto, centavos):
        assert CampoReais(required=False).clean(texto) == centavos

    def test_recusa_texto(self):
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            CampoReais().clean("doze reais")


def _dados_peca(categoria, **extra):
    dados = {
        "nome": "Polvo Marinho",
        "categoria": str(categoria.pk),
        "status": "ativo",
        "descricao": "Polvo de crochê",
        "preco_centavos": "89,90",
        "preco_promocional_centavos": "",
        "custo_centavos": "",
        "disponibilidade": "pronta_entrega",
        "prazo_producao_dias": "",
        "material": "Algodão",
        "cuidados": "",
        "peso_g": "200",
        "altura_cm": "10",
        "largura_cm": "10",
        "comprimento_cm": "10",
        "variacoes-TOTAL_FORMS": "1",
        "variacoes-INITIAL_FORMS": "0",
        "variacoes-0-cor": "Lilás",
        "variacoes-0-cor_hex": "#a58bc4",
        "variacoes-0-tamanho": "",
        "variacoes-0-preco_ajuste_centavos": "",
        "variacoes-0-ativa": "on",
        "variacoes-0-sku": "",
        "variacoes-0-estoque_inicial": "3",
        "ficha-TOTAL_FORMS": "1",
        "ficha-INITIAL_FORMS": "0",
        "ficha-0-nome": "Altura",
        "ficha-0-valor": "10 cm",
    }
    dados.update(extra)
    return dados


@pytest.mark.django_db
class TestPecas:
    def test_cadastra_peca_com_variacao_estoque_e_ficha(self, equipe, categoria, admin_usuario):
        resposta = equipe.post("/gestao/pecas/nova/", _dados_peca(categoria))
        produto = Produto.objects.get(nome="Polvo Marinho")
        assert resposta.url == f"/gestao/pecas/{produto.pk}/"
        assert produto.preco_centavos == 8990 and produto.slug == "polvo-marinho"
        assert produto.publicado_em is not None
        variacao = produto.variacoes.get()
        assert variacao.sku == "POLVO-MARINHO-LILAS" and variacao.estoque == 3
        assert variacao.movimentacoes.get().autor == admin_usuario
        assert produto.especificacoes.get().valor == "10 cm"
        assert "lilas" in Produto.objects.get(pk=produto.pk).busca

    def test_exige_uma_variacao(self, equipe, categoria):
        dados = _dados_peca(categoria, **{"variacoes-0-cor": "", "variacoes-0-cor_hex": ""})
        dados.pop("variacoes-0-estoque_inicial")
        dados.pop("variacoes-0-ativa")
        resposta = equipe.post("/gestao/pecas/nova/", dados)
        assert resposta.status_code == 200
        assert "pelo menos uma variação ativa" in resposta.content.decode()

    def test_promocao_maior_que_o_preco(self, equipe, categoria):
        dados = _dados_peca(categoria, preco_promocional_centavos="99,90")
        resposta = equipe.post("/gestao/pecas/nova/", dados)
        assert "precisa ser menor" in resposta.content.decode()

    def test_edita_sem_mexer_no_estoque(self, equipe, produto, variacao, com_estoque):
        com_estoque(variacao, 2)
        slug_original = produto.slug  # renaming must not break links already shared
        dados = _dados_peca(
            produto.categoria,
            nome="Novo nome",
            **{
                "variacoes-TOTAL_FORMS": "1",
                "variacoes-INITIAL_FORMS": "1",
                "variacoes-0-id": str(variacao.pk),
                "variacoes-0-sku": variacao.sku,
                "variacoes-0-cor": "Azul",
                "ficha-TOTAL_FORMS": "0",
            },
        )
        dados.pop("variacoes-0-estoque_inicial")
        equipe.post(f"/gestao/pecas/{produto.pk}/", dados)
        produto.refresh_from_db()
        variacao.refresh_from_db()
        assert produto.nome == "Novo nome" and produto.slug == slug_original
        assert variacao.cor == "Azul" and variacao.estoque == 2

    def test_lanca_entrada_e_saida_de_estoque(self, equipe, produto, variacao):
        url = f"/gestao/pecas/{produto.pk}/estoque/"
        equipe.post(url, {"variacao": variacao.pk, "quantidade": "4", "motivo": "terminei"})
        equipe.post(url, {"variacao": variacao.pk, "quantidade": "-1", "motivo": "manchou"})
        variacao.refresh_from_db()
        assert variacao.estoque == 3
        resposta = equipe.post(url, {"variacao": variacao.pk, "quantidade": "-10"}, follow=True)
        variacao.refresh_from_db()
        assert variacao.estoque == 3
        assert "mensagem--error" in resposta.content.decode()

    def test_fotos_enviar_principal_e_apagar(self, equipe, produto, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        fotos = [_foto("a.png"), _foto("b.png")]
        equipe.post(f"/gestao/pecas/{produto.pk}/fotos/", {"fotos": fotos})
        primeira, segunda = produto.fotos.order_by("ordem")
        assert primeira.texto_alternativo == produto.nome and segunda.ordem == 2

        equipe.post(f"/gestao/pecas/{produto.pk}/fotos/{segunda.pk}/principal/")
        assert list(produto.fotos.order_by("ordem")) == [segunda, primeira]

        equipe.post(f"/gestao/pecas/{produto.pk}/fotos/{primeira.pk}/apagar/")
        assert list(ProdutoFoto.objects.filter(produto=produto)) == [segunda]

    def test_busca_e_filtro(self, equipe, criar_produto):
        criar_produto(nome="Coração de Crochê", slug="coracao", status="ativo")
        criar_produto(nome="Bolsa Praia", slug="bolsa", status="rascunho")
        html = equipe.get("/gestao/pecas/?q=CORACAO").content.decode()
        assert "Coração de Crochê" in html and "Bolsa Praia" not in html
        html = equipe.get("/gestao/pecas/?status=rascunho").content.decode()
        assert "Bolsa Praia" in html and "Coração de Crochê" not in html


@pytest.mark.django_db
class TestAvaliacoes:
    def test_publicar_com_resposta(self, equipe, produto, cliente):
        avaliacao = Avaliacao.objects.create(produto=produto, autor=cliente, nota=5)
        resposta = equipe.post(
            f"/gestao/avaliacoes/{avaliacao.pk}/",
            {"acao": "publicar", "resposta_loja": "Obrigada!", "voltar_status": "pendente"},
        )
        avaliacao.refresh_from_db()
        assert avaliacao.status == Avaliacao.Status.PUBLICADA
        assert avaliacao.resposta_loja == "Obrigada!"
        assert resposta.url == "/gestao/avaliacoes/?status=pendente"

    def test_ocultar(self, equipe, produto, cliente):
        avaliacao = Avaliacao.objects.create(
            produto=produto, autor=cliente, nota=1, status=Avaliacao.Status.PUBLICADA
        )
        equipe.post(f"/gestao/avaliacoes/{avaliacao.pk}/", {"acao": "ocultar"})
        avaliacao.refresh_from_db()
        assert avaliacao.status == Avaliacao.Status.OCULTA


@pytest.mark.django_db
class TestPainelCompleto:
    def test_admin_com_tema_e_csp_proprio(self, equipe, settings):
        resposta = equipe.get(f"/{settings.ADMIN_URL}")
        assert resposta.status_code == 200
        assert "unsafe-eval" in resposta["Content-Security-Policy"]
        assert "unfold" in resposta.content.decode()

    def test_loja_e_gestao_mantem_a_csp_rigida(self, equipe):
        for url in ["/", "/gestao/"]:
            politica = equipe.get(url)["Content-Security-Policy"]
            assert "unsafe-eval" not in politica and "unsafe-inline" not in politica
