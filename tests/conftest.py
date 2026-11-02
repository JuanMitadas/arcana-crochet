import pytest

from apps.catalogo.models import Categoria, Produto, ProdutoVariacao
from apps.contas.models import Usuario


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
