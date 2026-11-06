import pytest

from apps.catalogo.estoque import registrar_movimentacao
from apps.catalogo.models import Categoria, MovimentacaoEstoque, Produto, ProdutoVariacao
from apps.contas.models import Endereco, Usuario


@pytest.fixture
def categoria(db):
    return Categoria.objects.create(nome="Amigurumi", slug="amigurumi")


@pytest.fixture
def criar_produto(categoria):
    def _criar(**campos):
        dados = {
            "categoria": categoria,
            "nome": "Urso de crochê",
            "slug": f"urso-{Produto.objects.count() + 1}",
            "preco_centavos": 12_990,
            "peso_g": 300,
            "altura_cm": 10,
            "largura_cm": 15,
            "comprimento_cm": 20,
            "status": Produto.Status.ATIVO,
        }
        dados.update(campos)
        return Produto.objects.create(**dados)

    return _criar


@pytest.fixture
def produto(criar_produto):
    return criar_produto()


@pytest.fixture
def variacao(produto):
    return ProdutoVariacao.objects.create(produto=produto, sku="URSO-AZ", cor="Azul")


@pytest.fixture
def admin_usuario(db):
    return Usuario.objects.create_superuser("admin@arcana.test", "senha-forte-123")


@pytest.fixture
def com_estoque():
    """Add ``quantidade`` units of stock to a variation."""

    def _entrada(variacao, quantidade):
        registrar_movimentacao(variacao, MovimentacaoEstoque.Tipo.ENTRADA_PRODUCAO, quantidade)
        variacao.refresh_from_db()
        return variacao

    return _entrada


@pytest.fixture
def cliente(db):
    from allauth.account.models import EmailAddress

    usuario = Usuario.objects.create_user(
        "cliente@teste.com", "senha-forte-123", nome_completo="Marina Alves"
    )
    EmailAddress.objects.create(user=usuario, email=usuario.email, verified=True, primary=True)
    return usuario


@pytest.fixture
def endereco(cliente):
    return Endereco.objects.create(
        usuario=cliente,
        destinatario="Marina Alves",
        telefone="11987654321",
        cep="01310100",
        logradouro="Avenida Paulista",
        numero="1000",
        bairro="Bela Vista",
        cidade="São Paulo",
        uf="SP",
        padrao=True,
    )
