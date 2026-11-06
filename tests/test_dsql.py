"""What changed for Aurora DSQL: search without extensions, OCC retries, migrations."""

import importlib
import pkgutil

import psycopg
import pytest
from django.apps import apps
from django.conf import settings
from django.db import OperationalError

from apps.catalogo.models import Categoria, Produto, ProdutoVariacao
from apps.core import transacoes
from apps.core.texto import normalizar, semelhanca
from apps.core.transacoes import atomico, conflito_occ


class TestTexto:
    def test_normalizar_tira_acentos_maiusculas_e_espacos(self):
        assert normalizar("  Coração   AZUL-Marinho ") == "coracao azul-marinho"
        assert normalizar("Crochê à mão") == "croche a mao"
        assert normalizar("") == ""

    def test_semelhanca_entre_palavras(self):
        assert semelhanca("urço", "Urso Ursolino") == 0.75
        assert semelhanca("bolsa", "Urso Ursolino") < 0.5


@pytest.mark.django_db
class TestColunaBusca:
    def test_produto_novo_ja_tem_texto_de_busca(self, criar_produto):
        produto = criar_produto(nome="Coração de Crochê", material="Algodão")
        assert produto.busca == "coracao de croche algodao amigurumi"

    def test_cor_nova_entra_na_busca(self, produto):
        ProdutoVariacao.objects.create(produto=produto, sku="X1", cor="Lilás")
        produto.refresh_from_db()
        assert "lilas" in produto.busca

        produto.variacoes.get().delete()
        produto.refresh_from_db()
        assert "lilas" not in produto.busca

    def test_save_com_update_fields_tambem_atualiza(self, produto):
        produto.nome = "Polvo"
        produto.save(update_fields=["nome"])
        produto.refresh_from_db()
        assert produto.busca.startswith("polvo")

    def test_categoria_renomeada_atualiza_produtos(self, produto, categoria):
        filha = Categoria.objects.create(nome="Ursos", slug="ursos", pai=categoria)
        outro = Produto.objects.create(
            categoria=filha,
            nome="Ursinho",
            slug="ursinho",
            preco_centavos=1000,
            peso_g=1,
            altura_cm=1,
            largura_cm=1,
            comprimento_cm=1,
        )
        categoria.nome = "Bichinhos"
        categoria.save()
        produto.refresh_from_db()
        outro.refresh_from_db()
        assert "bichinhos" in produto.busca and "bichinhos" in outro.busca

    def test_busca_pela_cor_sem_acento(self, client, produto):
        ProdutoVariacao.objects.create(produto=produto, sku="X2", cor="Pêssego")
        assert produto.nome in client.get("/busca/?q=PESSEGO").content.decode()

    def test_sugere_parecidos_quando_nao_acha(self, client, criar_produto):
        criar_produto(nome="Urso Ursolino", slug="ursolino")
        resposta = client.get("/busca/?q=urço")
        assert [p.nome for p in resposta.context["sugestoes"]] == ["Urso Ursolino"]
        assert client.get("/busca/?q=xyzw").context["sugestoes"] == []


def erro_occ(codigo="OC000"):
    """An OCC conflict as Django raises it, wrapping the psycopg error."""
    erro = OperationalError(f"change conflicts with another transaction ({codigo})")
    erro.__cause__ = psycopg.errors.SerializationFailure("conflict")
    return erro


class TestAtomico:
    @pytest.fixture(autouse=True)
    def sem_espera(self, monkeypatch):
        monkeypatch.setattr(transacoes.time, "sleep", lambda segundos: None)

    def test_reconhece_conflitos(self):
        assert conflito_occ(erro_occ())
        assert conflito_occ(OperationalError("schema updated by another transaction (OC001)"))
        assert not conflito_occ(OperationalError("connection refused"))

    @pytest.mark.django_db(transaction=True)
    def test_repete_depois_de_conflito(self):
        chamadas = []

        @atomico
        def operacao():
            chamadas.append(1)
            if len(chamadas) < 3:
                raise erro_occ()
            return "ok"

        assert operacao() == "ok"
        assert len(chamadas) == 3

    @pytest.mark.django_db(transaction=True)
    def test_desiste_depois_das_tentativas(self):
        @atomico(tentativas=2)
        def operacao():
            raise erro_occ()

        with pytest.raises(OperationalError):
            operacao()

    @pytest.mark.django_db(transaction=True)
    def test_outros_erros_nao_repetem(self):
        chamadas = []

        @atomico
        def operacao():
            chamadas.append(1)
            raise OperationalError("connection refused")

        with pytest.raises(OperationalError):
            operacao()
        assert len(chamadas) == 1

    @pytest.mark.django_db
    def test_dentro_de_outra_transacao_so_propaga(self):
        chamadas = []

        @atomico
        def operacao():
            chamadas.append(1)
            raise erro_occ()

        # pytest-django already runs this test inside a transaction.
        with pytest.raises(OperationalError):
            operacao()
        assert len(chamadas) == 1


@pytest.mark.parametrize("app_label", sorted(settings.MIGRATION_MODULES))
def test_migracoes_reconstruidas_tem_os_mesmos_nomes(app_label):
    """Fails after a Django/allauth upgrade adds a migration: run migracoes_dsql."""

    def nomes(pacote):
        modulo = importlib.import_module(pacote)
        return sorted(nome for _, nome, _ in pkgutil.iter_modules(modulo.__path__))

    original = nomes(apps.get_app_config(app_label).name + ".migrations")
    assert nomes(settings.MIGRATION_MODULES[app_label]) == original


def test_motor_dsql_cria_indices_unicos_condicionais_com_async():
    from config.dsql.base import DatabaseWrapper

    sql = DatabaseWrapper.SchemaEditorClass.sql_create_unique_index
    assert sql.startswith("CREATE UNIQUE INDEX ASYNC ") and "%(condition)s" in sql
