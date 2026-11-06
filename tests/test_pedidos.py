import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError

from apps.avaliacoes.models import Avaliacao
from apps.catalogo.models import Produto, ProdutoVariacao
from apps.pedidos import servicos
from apps.pedidos.carrinho import Carrinho
from apps.pedidos.models import Cupom, Pedido


class Requisicao:
    def __init__(self):
        self.session = SessionStore()


@pytest.fixture
def carrinho():
    return Carrinho(Requisicao())


@pytest.fixture
def pronta(variacao, com_estoque):
    return com_estoque(variacao, 2)


def _fechar(cliente, endereco, carrinho, metodo="pix", parcelas=1):
    carrinho.cep = endereco.cep
    carrinho.salvar()
    return servicos.criar_pedido(cliente, carrinho, endereco, metodo, parcelas)


class TestCarrinho:
    def test_nao_passa_do_estoque(self, carrinho, pronta):
        assert carrinho.adicionar(pronta, 5) == 2
        assert carrinho.quantidade_total == 2

    def test_sob_encomenda_aceita_ate_dez(self, carrinho, criar_produto):
        produto = criar_produto(disponibilidade="sob_encomenda", prazo_producao_dias=7)
        v = ProdutoVariacao.objects.create(produto=produto, sku="ENC-1")
        assert carrinho.adicionar(v, 15) == 10

    def test_item_que_esgotou_e_ajustado(self, carrinho, pronta, com_estoque):
        carrinho.adicionar(pronta, 2)
        servicos.registrar_movimentacao(pronta, "venda", -1)
        novo = Carrinho(carrinho)  # same session
        assert novo.itens[0].quantidade == 1
        assert novo.ajustado

    def test_cupom_percentual_e_minimo(self, carrinho, pronta):
        Cupom.objects.create(codigo="DEZ", tipo="percentual", valor=10, minimo_centavos=20000)
        carrinho.adicionar(pronta, 1)
        carrinho.cupom_codigo = "dez".upper()
        carrinho.salvar()
        assert "a partir de" in carrinho.cupom_erro
        carrinho.adicionar(pronta, 1)
        assert carrinho.desconto_cupom_centavos == 2598

    def test_cupom_frete_gratis_zera_o_pac(self, carrinho, pronta):
        Cupom.objects.create(codigo="FRETE", tipo="frete_gratis")
        carrinho.adicionar(pronta, 1)
        carrinho.cep = "01310100"
        carrinho.cupom_codigo = "FRETE"
        carrinho.salvar()
        assert carrinho.frete.codigo == "pac" and carrinho.frete_centavos == 0


class TestCicloDoPedido:
    def test_criar_pedido_reserva_estoque_e_esvazia_sacola(
        self, cliente, endereco, carrinho, pronta
    ):
        carrinho.adicionar(pronta, 2)
        pedido = _fechar(cliente, endereco, carrinho)
        pronta.refresh_from_db()
        assert pedido.status == Pedido.Status.AGUARDANDO_PAGAMENTO
        assert pedido.codigo.startswith("ARC-")
        assert pronta.estoque == 2 and pronta.estoque_reservado == 2
        assert pronta.produto.__class__.objects.get(pk=pronta.produto_id).status == "esgotado"
        assert carrinho.quantidade_total == 0 or not Carrinho(carrinho).itens

    def test_totais_com_pix(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho, metodo="pix")
        assert pedido.desconto_pix_centavos == 12990 - 12341
        assert pedido.total_centavos == 12341 + pedido.frete_centavos
        assert pedido.parcelas == 1

    def test_cartao_limita_parcelas(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho, metodo="cartao", parcelas=12)
        assert pedido.parcelas == 3
        assert pedido.desconto_pix_centavos == 0

    def test_pagamento_baixa_estoque_definitivo(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        pronta.refresh_from_db()
        assert pedido.status == Pedido.Status.PAGO and pedido.pago_em
        assert (pronta.estoque, pronta.estoque_reservado) == (1, 0)
        assert pronta.movimentacoes.filter(tipo="venda").count() == 1

    def test_enviar_exige_rastreio(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        pedido = servicos.avancar(pedido)
        assert pedido.status == Pedido.Status.EM_SEPARACAO
        with pytest.raises(ValidationError):
            servicos.avancar(pedido)
        pedido = servicos.avancar(pedido, codigo_rastreio="aa123456789br")
        assert pedido.status == Pedido.Status.ENVIADO
        assert pedido.codigo_rastreio == "AA123456789BR"
        pedido = servicos.avancar(pedido)
        assert pedido.status == Pedido.Status.ENTREGUE
        assert [e["estado"] for e in pedido.linha_do_tempo()] == ["concluida"] * 4

    def test_cancelar_antes_de_pagar_libera_reserva(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 2)
        pedido = servicos.cancelar(_fechar(cliente, endereco, carrinho))
        pronta.refresh_from_db()
        assert pedido.status == Pedido.Status.CANCELADO
        assert (pronta.estoque, pronta.estoque_reservado) == (2, 0)
        assert Produto.objects.get(pk=pronta.produto_id).status == Produto.Status.ATIVO

    def test_cancelar_depois_de_pago_devolve_ao_estoque(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        servicos.cancelar(pedido)
        pronta.refresh_from_db()
        assert pronta.estoque == 2

    def test_nao_cancela_pedido_enviado(self, cliente, endereco, carrinho, pronta):
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        pedido = servicos.avancar(servicos.avancar(pedido), codigo_rastreio="AA1BR")
        with pytest.raises(ValidationError):
            servicos.cancelar(pedido)

    def test_cupom_conta_uso(self, cliente, endereco, carrinho, pronta):
        cupom = Cupom.objects.create(codigo="ARC", tipo="fixo", valor=1000)
        carrinho.adicionar(pronta, 1)
        carrinho.cupom_codigo = "ARC"
        pedido = _fechar(cliente, endereco, carrinho, metodo="cartao")
        cupom.refresh_from_db()
        assert cupom.usos == 1
        assert pedido.desconto_cupom_centavos == 1000


@pytest.mark.django_db
class TestTelas:
    def test_sacola_adicionar_e_atualizar(self, client, pronta):
        resposta = client.post("/sacola/adicionar/", {"variacao": pronta.pk, "quantidade": 1})
        assert resposta.status_code == 302
        conteudo = client.get("/sacola/").content.decode()
        assert pronta.produto.nome in conteudo
        resposta = client.post(
            f"/sacola/item/{pronta.pk}/", {"acao": "mais"}, headers={"HX-Request": "true"}
        )
        assert 'value="2"' in resposta.content.decode()
        assert "<html" not in resposta.content.decode()

    def test_comprar_agora_vai_para_o_checkout(self, client, pronta):
        resposta = client.post(
            "/sacola/adicionar/", {"variacao": pronta.pk, "quantidade": 1, "acao": "comprar"}
        )
        assert resposta.url == "/checkout/"

    def test_frete_na_pagina_do_produto(self, client, produto):
        resposta = client.post(
            f"/p/{produto.slug}/frete/", {"cep": "01310-100"}, headers={"HX-Request": "true"}
        )
        assert "PAC" in resposta.content.decode() and "SEDEX" in resposta.content.decode()

    def test_checkout_completo(self, client, cliente, endereco, pronta):
        client.post("/sacola/adicionar/", {"variacao": pronta.pk, "quantidade": 1})
        assert client.get("/checkout/").url == "/checkout/identificacao/"
        client.force_login(cliente)
        assert client.get("/checkout/").url == "/checkout/entrega/"
        resposta = client.post(
            "/checkout/entrega/", {"endereco": str(endereco.pk), "frete": "sedex"}
        )
        assert resposta.url == "/checkout/pagamento/"
        resposta = client.post("/checkout/pagamento/", {"metodo": "cartao", "parcelas": "2"})
        assert resposta.url == "/checkout/revisao/"
        assert "2x de" in client.get("/checkout/revisao/").content.decode()
        resposta = client.post("/checkout/revisao/", {"aceite": "1"})
        pedido = Pedido.objects.get(cliente=cliente)
        assert resposta.url == f"{pedido.get_absolute_url()}?novo=1"
        assert pedido.frete_servico == "SEDEX" and pedido.parcelas == 2
        assert "Pedido recebido" in client.get(resposta.url).content.decode()

    def test_checkout_cadastra_endereco_novo(self, client, cliente, pronta):
        client.force_login(cliente)
        client.post("/sacola/adicionar/", {"variacao": pronta.pk, "quantidade": 1})
        resposta = client.post(
            "/checkout/entrega/",
            {
                "endereco": "novo",
                "novo-cep": "20040-002",
                "novo-logradouro": "Rua da Assembleia",
                "novo-numero": "10",
                "novo-bairro": "Centro",
                "novo-cidade": "Rio de Janeiro",
                "novo-uf": "RJ",
                "novo-destinatario": "Marina",
                "novo-telefone": "(21) 99999-0000",
            },
        )
        assert resposta.url == "/checkout/pagamento/"
        assert cliente.enderecos.get().padrao

    def test_pedido_de_outra_pessoa_nao_abre(self, client, cliente, endereco, pronta):
        carrinho = Carrinho(Requisicao())
        carrinho.adicionar(pronta, 1)
        pedido = _fechar(cliente, endereco, carrinho)
        from apps.contas.models import Usuario

        intrusa = Usuario.objects.create_user("outra@teste.com", "senha-forte-123")
        client.force_login(intrusa)
        assert client.get(pedido.get_absolute_url()).status_code == 404

    def test_avaliar_so_depois_de_entregue(self, client, cliente, endereco, pronta):
        carrinho = Carrinho(Requisicao())
        carrinho.adicionar(pronta, 1)
        pedido = servicos.marcar_pago(_fechar(cliente, endereco, carrinho))
        item = pedido.itens.get()
        client.force_login(cliente)
        assert client.get(f"/minha-conta/avaliar/{item.pk}/").status_code == 403
        pedido = servicos.avancar(servicos.avancar(pedido), codigo_rastreio="AA1BR")
        servicos.avancar(pedido)
        resposta = client.post(
            f"/minha-conta/avaliar/{item.pk}/", {"nota": "5", "comentario": "Linda!"}
        )
        assert resposta.status_code == 302
        avaliacao = Avaliacao.objects.get(item=item)
        assert avaliacao.status == Avaliacao.Status.PENDENTE and avaliacao.compra_verificada

    def test_minha_conta_exige_login(self, client):
        assert client.get("/minha-conta/").status_code == 302


@pytest.mark.django_db
class TestBusca:
    def test_busca_ignora_acentos(self, client, criar_produto):
        criar_produto(nome="Coração de crochê", slug="coracao")
        criar_produto(nome="Bolsa", slug="bolsa")
        conteudo = client.get("/busca/?q=coracao").content.decode()
        assert "Coração de crochê" in conteudo and ">Bolsa<" not in conteudo

    def test_filtro_de_preco_e_ordem(self, client, criar_produto):
        criar_produto(nome="Barato", slug="barato", preco_centavos=3000)
        criar_produto(nome="Caro", slug="caro", preco_centavos=30000)
        conteudo = client.get("/loja/?preco_max=100&ordem=menor_preco").content.decode()
        assert "Barato" in conteudo and ">Caro<" not in conteudo

    def test_filtro_por_cor(self, client, criar_produto):
        azul = criar_produto(nome="Peça azul", slug="azul")
        rosa = criar_produto(nome="Peça rosa", slug="rosa")
        ProdutoVariacao.objects.create(produto=azul, sku="AZ", cor="Azul")
        ProdutoVariacao.objects.create(produto=rosa, sku="RO", cor="Rosa")
        conteudo = client.get("/loja/?cor=Azul").content.decode()
        assert "Peça azul" in conteudo and "Peça rosa" not in conteudo


@pytest.mark.django_db
def test_popular_demo_cria_loja_navegavel(client, settings, tmp_path):
    from django.core.management import call_command

    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path
    call_command("popular_demo")
    assert Produto.objects.count() == 14
    assert Pedido.objects.filter(status=Pedido.Status.ENVIADO).exists()
    assert Avaliacao.objects.filter(status="publicada").exists()
    for url in ["/", "/loja/", "/c/amigurumis/", "/p/urso-ursolino/", "/busca/?q=urso"]:
        assert client.get(url).status_code == 200, url
