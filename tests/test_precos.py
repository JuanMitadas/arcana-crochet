import pytest

from apps.core import precos
from apps.pedidos import frete


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [(10000, 9500), (12990, 12341), (100, 95), (1, 1)],
)
def test_preco_pix_arredonda_meio_centavo_para_cima(centavos, esperado):
    assert precos.preco_pix(centavos) == esperado


@pytest.mark.parametrize(
    ("centavos", "vezes", "parcela"),
    [(12990, 3, 4330), (5990, 2, 2995), (3990, 1, 3990), (1000, 1, 1000)],
)
def test_parcelamento_respeita_parcela_minima(centavos, vezes, parcela):
    p = precos.parcelamento(centavos)
    assert (p.vezes, p.valor_parcela_centavos) == (vezes, parcela)


def test_opcoes_de_parcelamento_vao_de_1x_ate_o_maximo():
    assert [o.vezes for o in precos.opcoes_parcelamento(12990)] == [1, 2, 3]


def test_percentual_de_desconto():
    assert precos.percentual_desconto(12000, 9000) == 25
    assert precos.percentual_desconto(12000, None) == 0


class TestFrete:
    def test_cep_invalido(self):
        with pytest.raises(ValueError):
            frete.cotar("123", 300, 10000)

    def test_pac_e_sedex_com_prazo_de_producao(self):
        pac, sedex = frete.cotar("01310-100", 300, 10000, prazo_extra_dias=10)
        assert pac.codigo == "pac" and sedex.codigo == "sedex"
        assert pac.prazo_dias == 4 + 10
        assert sedex.preco_centavos > pac.preco_centavos > 0

    def test_frete_gratis_no_pac_acima_do_limite(self):
        pac, sedex = frete.cotar("90000000", 300, 30000)
        assert pac.gratis and pac.preco_centavos == 0
        assert not sedex.gratis

    def test_peso_extra_encarece(self):
        leve = frete.cotar("40000000", 300, 1000)[0].preco_centavos
        pesado = frete.cotar("40000000", 2500, 1000)[0].preco_centavos
        assert pesado > leve
