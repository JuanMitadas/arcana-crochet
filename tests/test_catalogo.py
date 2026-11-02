import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalogo.estoque import EstoqueInsuficiente, registrar_movimentacao
from apps.catalogo.models import MovimentacaoEstoque, Produto, ProdutoVariacao

Tipo = MovimentacaoEstoque.Tipo


class TestRestricoesDoBanco:
    def test_preco_precisa_ser_positivo(self, criar_produto):
        with pytest.raises(IntegrityError), transaction.atomic():
            criar_produto(preco_centavos=0)

    def test_promocao_precisa_ser_menor_que_o_preco(self, criar_produto):
        with pytest.raises(IntegrityError), transaction.atomic():
            criar_produto(preco_centavos=10_000, preco_promocional_centavos=10_000)

    def test_sob_encomenda_exige_prazo_de_producao(self, criar_produto):
        with pytest.raises(IntegrityError), transaction.atomic():
            criar_produto(disponibilidade=Produto.Disponibilidade.SOB_ENCOMENDA)
        produto = criar_produto(
            disponibilidade=Produto.Disponibilidade.SOB_ENCOMENDA, prazo_producao_dias=10
        )
        assert produto.pk


class TestPrecos:
    def test_preco_atual_usa_promocao(self, criar_produto):
        produto = criar_produto(preco_centavos=10_000, preco_promocional_centavos=8_000)
        assert produto.preco_atual_centavos == 8_000
        assert produto.em_promocao

    def test_variacao_soma_ajuste_ao_preco(self, produto):
        variacao = ProdutoVariacao.objects.create(
            produto=produto, sku="URSO-G", tamanho="G", preco_ajuste_centavos=1_500
        )
        assert variacao.preco_centavos == 12_990 + 1_500


class TestEstoque:
    def test_entrada_e_saida_atualizam_estoque_e_historico(self, variacao, admin_usuario):
        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 3, autor=admin_usuario)
        registrar_movimentacao(variacao, Tipo.VENDA, -1)
        variacao.refresh_from_db()
        assert variacao.estoque == 2
        assert list(
            variacao.movimentacoes.order_by("criado_em").values_list(
                "quantidade", "estoque_resultante"
            )
        ) == [(3, 3), (-1, 2)]

    def test_saida_maior_que_o_estoque_e_recusada(self, variacao):
        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 1)
        with pytest.raises(EstoqueInsuficiente):
            registrar_movimentacao(variacao, Tipo.VENDA, -2)
        variacao.refresh_from_db()
        assert variacao.estoque == 1
        assert variacao.movimentacoes.count() == 1

    def test_quantidade_zero_e_recusada(self, variacao):
        with pytest.raises(ValidationError):
            registrar_movimentacao(variacao, Tipo.AJUSTE, 0)

    def test_produto_esgota_e_volta_sozinho(self, produto, variacao):
        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 1)
        registrar_movimentacao(variacao, Tipo.VENDA, -1)
        produto.refresh_from_db()
        assert produto.status == Produto.Status.ESGOTADO

        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 2)
        produto.refresh_from_db()
        assert produto.status == Produto.Status.ATIVO

    def test_sob_encomenda_nunca_esgota(self, criar_produto):
        produto = criar_produto(
            disponibilidade=Produto.Disponibilidade.SOB_ENCOMENDA, prazo_producao_dias=7
        )
        variacao = ProdutoVariacao.objects.create(produto=produto, sku="SOB-1")
        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 1)
        registrar_movimentacao(variacao, Tipo.VENDA, -1)
        produto.refresh_from_db()
        assert produto.status == Produto.Status.ATIVO

    def test_rascunho_nao_muda_de_status(self, criar_produto):
        produto = criar_produto(status=Produto.Status.RASCUNHO)
        variacao = ProdutoVariacao.objects.create(produto=produto, sku="RASC-1")
        registrar_movimentacao(variacao, Tipo.ENTRADA_PRODUCAO, 1)
        registrar_movimentacao(variacao, Tipo.VENDA, -1)
        produto.refresh_from_db()
        assert produto.status == Produto.Status.RASCUNHO


class TestVitrine:
    def test_mostra_so_produtos_visiveis(self, client, criar_produto):
        criar_produto(nome="Urso ativo", slug="urso-ativo")
        criar_produto(nome="Urso rascunho", slug="urso-rascunho", status=Produto.Status.RASCUNHO)
        conteudo = client.get("/").content.decode()
        assert "Urso ativo" in conteudo
        assert "Urso rascunho" not in conteudo

    def test_requisicao_htmx_devolve_so_a_grade(self, client, produto):
        resposta = client.get("/", headers={"HX-Request": "true"})
        conteudo = resposta.content.decode()
        assert 'id="grade"' in conteudo
        assert "<html" not in conteudo

    def test_detalhe_do_produto(self, client, produto, variacao):
        resposta = client.get(produto.get_absolute_url())
        assert resposta.status_code == 200
        assert "R$ 129,90" in resposta.content.decode()

    def test_rascunho_nao_tem_pagina_publica(self, client, criar_produto):
        produto = criar_produto(status=Produto.Status.RASCUNHO)
        assert client.get(produto.get_absolute_url()).status_code == 404


class TestPainel:
    def test_paginas_do_painel_abrem(self, client, admin_usuario, produto, variacao):
        client.force_login(admin_usuario)
        for url in [
            "/admin/",
            "/admin/catalogo/produto/",
            f"/admin/catalogo/produto/{produto.pk}/change/",
            "/admin/catalogo/movimentacaoestoque/add/",
            "/admin/contas/usuario/add/",
        ]:
            assert client.get(url).status_code == 200, url

    def test_movimentacao_pelo_painel_altera_estoque(self, client, admin_usuario, variacao):
        client.force_login(admin_usuario)
        resposta = client.post(
            "/admin/catalogo/movimentacaoestoque/add/",
            {"variacao": variacao.pk, "tipo": Tipo.ENTRADA_PRODUCAO, "quantidade": 4},
        )
        assert resposta.status_code == 302
        variacao.refresh_from_db()
        assert variacao.estoque == 4
        assert variacao.movimentacoes.get().autor == admin_usuario

    def test_painel_recusa_saida_sem_estoque(self, client, admin_usuario, variacao):
        client.force_login(admin_usuario)
        resposta = client.post(
            "/admin/catalogo/movimentacaoestoque/add/",
            {"variacao": variacao.pk, "tipo": Tipo.VENDA, "quantidade": -1},
        )
        assert resposta.status_code == 200
        assert "Estoque insuficiente" in resposta.content.decode()
        assert variacao.movimentacoes.count() == 0
