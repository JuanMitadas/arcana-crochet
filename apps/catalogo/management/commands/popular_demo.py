"""Fill the store with demo data (development only).

    python manage.py popular_demo            # creates it if it doesn't exist yet
    python manage.py popular_demo --limpar   # deletes the demo data and recreates it
    python manage.py popular_demo --pecas 3  # only 3 pieces, no customers or orders

Creates categories, pieces with generated illustrations, stock, coupons, a test
customer (cliente@arcana.test / arcana-demo-123) with orders at several stages, and
published reviews. With --pecas, only that many pieces (from different categories)
and their categories: handy to show the published store without fake orders.
"""

import random
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.avaliacoes.models import Avaliacao
from apps.catalogo.demo_imagens import ilustrar
from apps.catalogo.estoque import registrar_movimentacao
from apps.catalogo.models import (
    Categoria,
    MovimentacaoEstoque,
    Produto,
    ProdutoEspecificacao,
    ProdutoFoto,
    ProdutoVariacao,
)
from apps.contas.models import Endereco, Usuario
from apps.pedidos import servicos
from apps.pedidos.carrinho import Carrinho
from apps.pedidos.models import Cupom, Pedido

CORES = {
    "Azul Arcana": "#17597c",
    "Verde-mar": "#2e7f83",
    "Petróleo": "#015d5c",
    "Creme": "#efe7cf",
    "Mostarda": "#d9a441",
    "Terracota": "#c8775a",
    "Rosa antigo": "#d8a1a4",
    "Lilás": "#a99bc9",
    "Cinza névoa": "#9aa3a6",
}

CATEGORIAS = [
    ("amigurumis", "Amigurumis", "Bichinhos e criaturas para abraçar.", None),
    ("bichinhos", "Bichinhos", "Ursos, coelhos e companhia.", "amigurumis"),
    ("seres-magicos", "Seres mágicos", "Criaturas do mar e do céu.", "amigurumis"),
    ("bolsas", "Bolsas", "Para levar o dia a dia com charme.", None),
    ("casa", "Casa", "Cestos e detalhes que aquecem.", None),
    ("acessorios", "Acessórios", "Gorros, cachecóis e mimos.", None),
]

# slug, name, category, shape, price, sale price, availability, lead time, colors,
# sizes, material, featured, stock per variation
PRODUTOS = [
    ("urso-ursolino", "Urso Ursolino", "bichinhos", "urso", 12990, None, "pronta_entrega", None,
     ["Azul Arcana", "Mostarda", "Terracota"], [], "Algodão egípcio", True, 3),
    ("coelha-lua", "Coelha Lua", "bichinhos", "coelho", 11990, 9990, "pronta_entrega", None,
     ["Mostarda", "Creme", "Rosa antigo"], [], "Algodão egípcio", True, 2),
    ("polvo-maresia", "Polvo Maresia", "seres-magicos", "polvo", 8990, None, "pronta_entrega",
     None, ["Terracota", "Lilás", "Verde-mar"], [], "Fio de algodão", False, 4),
    ("baleia-celeste", "Baleia Celeste", "seres-magicos", "baleia", 14990, 12990,
     "pronta_entrega", None, ["Verde-mar", "Azul Arcana"], [], "Algodão egípcio", True, 1),
    ("estrela-guia", "Estrela-guia (chaveiro)", "seres-magicos", "estrela", 3990, None,
     "pronta_entrega", None, ["Lilás", "Mostarda", "Verde-mar"], [], "Fio de algodão", False, 8),
    ("bolsa-portal", "Bolsa Portal", "bolsas", "bolsa", 18990, None, "sob_encomenda", 12,
     ["Rosa antigo", "Creme", "Azul Arcana"], [], "Fio náutico", True, 0),
    ("bolsa-mare", "Bolsa Maré", "bolsas", "bolsa", 15990, 13590, "pronta_entrega", None,
     ["Verde-mar", "Terracota"], [], "Fio de malha", False, 2),
    ("cesto-orvalho", "Cesto Orvalho", "casa", "cesto", 9990, None, "pronta_entrega", None,
     ["Creme", "Cinza névoa"], ["P", "M", "G"], "Fio de malha", True, 3),
    ("cesto-floresta", "Cesto Floresta", "casa", "cesto", 7990, 6790, "pronta_entrega", None,
     ["Petróleo", "Verde-mar"], ["P", "M"], "Barbante cru", False, 2),
    ("porta-copos-runa", "Porta-copos Runa (kit 4)", "casa", "porta_copos", 5990, None,
     "pronta_entrega", None, ["Cinza névoa", "Creme", "Mostarda"], [], "Barbante", False, 6),
    ("gorro-bruma", "Gorro Bruma", "acessorios", "gorro", 8990, None, "sob_encomenda", 7,
     ["Petróleo", "Azul Arcana", "Terracota"], ["Infantil", "Adulto"], "Lã merino", True, 0),
    ("cachecol-aurora", "Cachecol Aurora", "acessorios", "cachecol", 11990, 9990,
     "pronta_entrega", None, ["Terracota", "Lilás"], [], "Lã merino", False, 2),
    ("urso-noturno", "Urso Noturno", "bichinhos", "urso", 13990, None, "pronta_entrega", None,
     ["Petróleo", "Cinza névoa"], [], "Algodão egípcio", False, 1),
    ("coelho-orvalho", "Coelho Orvalho", "bichinhos", "coelho", 10990, None, "sob_encomenda", 10,
     ["Creme", "Lilás", "Verde-mar"], [], "Algodão egípcio", False, 0),
]  # fmt: skip

DESCRICOES = {
    "urso": "Um companheiro fofinho, tecido ponto a ponto com fio macio e enchimento antialérgico. Olhinhos bordados (sem peças pequenas), seguro para bebês.",
    "coelho": "Orelhas compridas, bochechas rosadas e um abraço que cabe na palma da mão. Perfeita para presentear ou decorar o quarto.",
    "polvo": "Os tentáculos em espiral acalmam e são ótimos para mãozinhas curiosas. Uma criatura do fundo do mar que veio morar na estante.",
    "baleia": "Grande, macia e serena. A Baleia Celeste nada entre almofadas e sonhos, com barriguinha em tom claro.",
    "estrela": "Um pequeno amuleto para chaves, mochilas ou bolsas. Cada estrela é única e tem um sorriso bordado.",
    "bolsa": "Estruturada e leve, com alça firme e fecho de botão. Cabe o celular, a carteira e um livro de bolso.",
    "cesto": "Para organizar fios, plantas, brinquedos ou o que precisar de um lugar bonito. Base firme que fica em pé sozinha.",
    "porta_copos": "Kit com quatro porta-copos em ponto concha. Protegem a mesa e deixam o café da tarde mais charmoso.",
    "gorro": "Quentinho, com pompom e barra canelada. Feito na cor e no tamanho que você escolher.",
    "cachecol": "Comprido o bastante para duas voltas, com franjas nas pontas. Lã macia que não pinica.",
}

AVALIACOES = [
    (5, "Ficou ainda mais lindo ao vivo", "Acabamento impecável, dá para ver o cuidado em cada ponto. Chegou bem embalado e com um bilhetinho."),
    (5, "Presente perfeito", "Dei para minha sobrinha e ela não larga mais. Muito macio."),
    (4, "Muito bonito", "Amei a cor. Achei um pouco menor do que imaginava, mas as medidas estavam na descrição."),
    (5, "Virei cliente", "Segunda compra aqui. A qualidade se mantém e a entrega foi rápida."),
    (5, None, "Lindo demais, parece que saiu de um livro de fantasia."),
    (3, "Bonito, mas demorou", "A peça é linda, mas o correio atrasou alguns dias."),
]  # fmt: skip

SENHA_DEMO = "arcana-demo-123"


def sortear_variadas(quantidade: int) -> list:
    """The first ``quantidade`` pieces, taking one from each top-level category in turn."""
    pais = {slug: pai or slug for slug, _, _, pai in CATEGORIAS}
    grupos: dict[str, list] = {}
    for linha in PRODUTOS:
        grupos.setdefault(pais[linha[2]], []).append(linha)
    escolhidas = []
    while len(escolhidas) < min(quantidade, len(PRODUTOS)):
        for grupo in grupos.values():
            if grupo and len(escolhidas) < quantidade:
                escolhidas.append(grupo.pop(0))
    return escolhidas


class Command(BaseCommand):
    help = "Fill the store with demo pieces, orders and reviews."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true", help="Delete the demo data first.")
        parser.add_argument(
            "--pecas",
            type=int,
            metavar="N",
            help="Only N pieces from different categories, without customers or orders.",
        )

    def handle(self, *args, limpar=False, pecas=None, **options):
        if not settings.DEBUG:
            raise CommandError("Development only (DEBUG=1).")
        if limpar:
            self._limpar()
        if pecas is not None and pecas < 1:
            raise CommandError("--pecas must be at least 1.")
        linhas = sortear_variadas(pecas) if pecas else PRODUTOS
        if Produto.objects.filter(slug__in=[linha[0] for linha in linhas]).exists():
            self.stdout.write("The demo data already exists. Use --limpar to recreate it.")
            return
        random.seed(7)
        with transaction.atomic():
            categorias = self._categorias({linha[2] for linha in linhas})
            produtos = self._produtos(categorias, linhas)
            if not pecas:
                self._cupons()
                self._pedidos_e_avaliacoes(produtos)
        if pecas:
            plural = "s" if len(produtos) > 1 else ""
            self.stdout.write(self.style.SUCCESS(f"Done: {len(produtos)} demo piece{plural}."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {len(produtos)} pieces. Test customer: cliente@arcana.test / {SENHA_DEMO}"
            )
        )

    # --- steps ------------------------------------------------------------

    def _limpar(self):
        demo = Usuario.objects.filter(email__endswith="@arcana.test").exclude(is_superuser=True)
        Avaliacao.objects.filter(autor__in=demo).delete()
        for pedido in Pedido.objects.filter(cliente__in=demo):
            pedido.itens.all().delete()
            pedido.delete()
        slugs = [p[0] for p in PRODUTOS]
        MovimentacaoEstoque.objects.filter(variacao__produto__slug__in=slugs).delete()
        for produto in Produto.objects.filter(slug__in=slugs):
            for foto in produto.fotos.all():
                foto.imagem.delete(save=False)
            produto.delete()
        for slug, *_ in reversed(CATEGORIAS):
            for cat in Categoria.objects.filter(slug=slug):
                if cat.imagem:
                    cat.imagem.delete(save=False)
                cat.delete()
        Cupom.objects.filter(codigo__in=["BEMVINDA10", "FRETEGRATIS", "ARCANA15"]).delete()
        demo.delete()
        self.stdout.write("Demo data deleted.")

    def _categorias(self, usadas):
        pais = {slug: pai for slug, _, _, pai in CATEGORIAS}
        necessarias = usadas | {pais[slug] for slug in usadas if pais[slug]}
        categorias = {}
        imagens = {
            "amigurumis": ("urso", "#17597c"),
            "bolsas": ("bolsa", "#d8a1a4"),
            "casa": ("cesto", "#efe7cf"),
            "acessorios": ("gorro", "#015d5c"),
        }
        for ordem, (slug, nome, descricao, pai) in enumerate(CATEGORIAS):
            if slug not in necessarias:
                continue
            cat = Categoria.objects.create(
                slug=slug, nome=nome, descricao=descricao, pai=categorias.get(pai), ordem=ordem
            )
            if slug in imagens:
                forma, cor = imagens[slug]
                cat.imagem.save(
                    f"{slug}.webp", ContentFile(ilustrar(forma, cor, seed=ordem + 40, zoom=1.25))
                )
            categorias[slug] = cat
        return categorias

    def _produtos(self, categorias, linhas):
        agora = timezone.now()
        produtos = []
        for i, linha in enumerate(linhas):
            (slug, nome, cat, forma, preco, promo, disp, prazo, cores, tamanhos, material,
             destaque, estoque) = linha  # fmt: skip
            produto = Produto.objects.create(
                slug=slug,
                nome=nome,
                categoria=categorias[cat],
                descricao=DESCRICOES[forma]
                + "\n\nCada peça é feita à mão pela Kamilly, então pequenas variações de"
                " cor e tamanho fazem parte do charme.",
                cuidados="Lave à mão, em água fria, com sabão neutro.\n"
                "Não torça: aperte com uma toalha e seque à sombra, na horizontal.",
                preco_centavos=preco,
                preco_promocional_centavos=promo,
                disponibilidade=disp,
                prazo_producao_dias=prazo,
                peso_g=random.choice([180, 250, 320, 450]),
                altura_cm=random.choice([8, 10, 12]),
                largura_cm=random.choice([15, 18, 20]),
                comprimento_cm=random.choice([20, 24, 28]),
                material=material,
                personalizavel=disp == "sob_encomenda",
                destaque=destaque,
                status=Produto.Status.ATIVO,
                publicado_em=agora - timedelta(days=i * 3),
            )
            medidas = {
                "urso": "28 cm de altura", "coelho": "32 cm com as orelhas", "polvo": "22 cm",
                "baleia": "35 cm de comprimento", "estrela": "9 cm", "bolsa": "24 × 20 × 8 cm",
                "cesto": "P 15 cm, M 20 cm, G 26 cm de diâmetro", "porta_copos": "11 cm de diâmetro",
                "gorro": "Infantil 46–50 cm, adulto 54–58 cm", "cachecol": "1,60 m × 18 cm",
            }  # fmt: skip
            for ordem, (nome_esp, valor) in enumerate(
                [
                    ("Medidas", medidas[forma]),
                    ("Ponto", random.choice(["Ponto baixo", "Ponto concha", "Ponto pipoca"])),
                    ("Enchimento", "Fibra siliconada antialérgica")
                    if forma in ("urso", "coelho", "polvo", "baleia", "estrela")
                    else ("Forro", "Tecido de algodão")
                    if forma == "bolsa"
                    else ("Acabamento", "Arremate escondido, sem nós aparentes"),
                ]
            ):
                ProdutoEspecificacao.objects.create(
                    produto=produto, nome=nome_esp, valor=valor, ordem=ordem
                )

            variacoes = []
            for cor in cores:
                for tamanho in tamanhos or [""]:
                    ajuste = {"P": -1500, "M": 0, "G": 2000, "Adulto": 1000}.get(tamanho, 0)
                    sku = f"{slug[:10].upper()}-{cor[:3].upper()}{'-' + tamanho[:3].upper() if tamanho else ''}"
                    v = ProdutoVariacao.objects.create(
                        produto=produto,
                        sku=sku.replace("É", "E").replace("Ó", "O"),
                        cor=cor,
                        cor_hex=CORES[cor],
                        tamanho=tamanho,
                        preco_ajuste_centavos=ajuste,
                    )
                    variacoes.append(v)
                    if estoque:
                        qtd = max(1, estoque - random.randint(0, 1))
                        registrar_movimentacao(
                            v, MovimentacaoEstoque.Tipo.ENTRADA_PRODUCAO, qtd, motivo="Demo"
                        )
            # Photos: one per color (linked to the variation) and a close-up of the first
            vistas = set()
            ordem = 1
            for v in variacoes:
                if v.cor in vistas:
                    continue
                vistas.add(v.cor)
                foto = ProdutoFoto(
                    produto=produto,
                    variacao=v,
                    texto_alternativo=f"{nome} de crochê na cor {v.cor.lower()}",
                    ordem=ordem,
                )
                foto.imagem.save(
                    f"{slug}-{ordem}.webp",
                    ContentFile(ilustrar(forma, CORES[v.cor], seed=i * 10 + ordem)),
                    save=False,
                )
                foto.save()
                ordem += 1
            close = ProdutoFoto(
                produto=produto,
                texto_alternativo=f"Detalhe dos pontos de {nome}",
                ordem=ordem,
            )
            close.imagem.save(
                f"{slug}-detalhe.webp",
                ContentFile(ilustrar(forma, CORES[cores[0]], seed=i * 10 + 9, zoom=2.4)),
                save=False,
            )
            close.save()
            produto.refresh_from_db()
            produtos.append(produto)
        return produtos

    def _cupons(self):
        Cupom.objects.create(codigo="BEMVINDA10", tipo=Cupom.Tipo.PERCENTUAL, valor=10)
        Cupom.objects.create(
            codigo="FRETEGRATIS", tipo=Cupom.Tipo.FRETE_GRATIS, minimo_centavos=15000
        )
        Cupom.objects.create(
            codigo="ARCANA15", tipo=Cupom.Tipo.FIXO, valor=1500, minimo_centavos=10000
        )

    def _pedidos_e_avaliacoes(self, produtos):
        cliente = Usuario.objects.create_user(
            "cliente@arcana.test", SENHA_DEMO, nome_completo="Marina Alves"
        )
        self._verificar_email(cliente)
        endereco = Endereco.objects.create(
            usuario=cliente, apelido="Casa", destinatario="Marina Alves",
            telefone="11987654321", cep="01310100", logradouro="Avenida Paulista",
            numero="1000", complemento="apto 42", bairro="Bela Vista", cidade="São Paulo",
            uf="SP", padrao=True,
        )  # fmt: skip

        outros = []
        for n, nome in enumerate(["Júlia Rocha", "Pedro Lima", "Ana Souza", "Beatriz Melo"]):
            u = Usuario.objects.create_user(
                f"compradora{n}@arcana.test", SENHA_DEMO, nome_completo=nome
            )
            e = Endereco.objects.create(
                usuario=u, destinatario=nome, telefone="21999990000", cep="20040002",
                logradouro="Rua da Assembleia", numero=str(10 + n), bairro="Centro",
                cidade="Rio de Janeiro", uf="RJ", padrao=True,
            )  # fmt: skip
            outros.append((u, e))

        prontos = [p for p in produtos if p.disponibilidade == "pronta_entrega"]
        # Delivered orders from other people, with published reviews
        for k, produto in enumerate(prontos[:9]):
            usuario, end = outros[k % len(outros)]
            pedido = self._comprar(usuario, end, [produto], metodo="pix")
            if pedido is None:
                continue
            self._ate(pedido, Pedido.Status.ENTREGUE, dias_atras=30 - k)
            for item in pedido.itens.all():
                nota, titulo, texto = AVALIACOES[k % len(AVALIACOES)]
                Avaliacao.objects.create(
                    produto=item.produto, item=item, autor=usuario, nota=nota,
                    titulo=titulo or "", comentario=texto, status=Avaliacao.Status.PUBLICADA,
                    resposta_loja="Obrigada pelo carinho! Fico muito feliz que gostou."
                    if k == 0 else "",
                )  # fmt: skip

        # The test customer's orders at different stages
        por_slug = {p.slug: p for p in produtos}
        etapas = [
            (["urso-ursolino"], Pedido.Status.ENVIADO, "cartao"),
            (["cesto-orvalho", "porta-copos-runa"], Pedido.Status.ENTREGUE, "pix"),
            (["bolsa-portal"], Pedido.Status.EM_SEPARACAO, "pix"),
            (["estrela-guia"], Pedido.Status.AGUARDANDO_PAGAMENTO, "pix"),
        ]
        for dias, (slugs, status, metodo) in enumerate(etapas):
            pedido = self._comprar(cliente, endereco, [por_slug[s] for s in slugs], metodo)
            if pedido:
                self._ate(pedido, status, dias_atras=12 - dias * 3)

    # --- helpers ----------------------------------------------------------

    def _verificar_email(self, usuario):
        from allauth.account.models import EmailAddress

        EmailAddress.objects.create(user=usuario, email=usuario.email, verified=True, primary=True)

    def _comprar(self, usuario, endereco, produtos, metodo):
        class Requisicao:
            session = SessionStore()

        carrinho = Carrinho(Requisicao())
        for produto in produtos:
            variacao = next(
                (
                    v
                    for v in produto.variacoes.all()
                    if produto.disponibilidade == "sob_encomenda" or v.disponivel > 0
                ),
                None,
            )
            if variacao:
                carrinho.adicionar(variacao, 1)
        if not carrinho.quantidade_total:
            return None
        carrinho.cep = endereco.cep
        carrinho.salvar()
        return servicos.criar_pedido(usuario, carrinho, endereco, metodo, parcelas=2)

    def _ate(self, pedido, status, dias_atras=5):
        if status == Pedido.Status.AGUARDANDO_PAGAMENTO:
            return
        pedido = servicos.marcar_pago(pedido)
        ordem = [Pedido.Status.EM_SEPARACAO, Pedido.Status.ENVIADO, Pedido.Status.ENTREGUE]
        for proximo in ordem[: ordem.index(status) + 1] if status in ordem else []:
            pedido = servicos.avancar(
                pedido, codigo_rastreio=f"AA{random.randint(100000000, 999999999)}BR"
            )
            if proximo == status:
                break
        # Spread the dates in the past so the timeline looks realistic
        base = timezone.now() - timedelta(days=dias_atras)
        campos = {"criado_em": base, "pago_em": base + timedelta(minutes=8)}
        if pedido.separado_em:
            campos["separado_em"] = base + timedelta(days=1)
        if pedido.enviado_em:
            campos["enviado_em"] = base + timedelta(days=2, hours=3)
        if pedido.entregue_em:
            campos["entregue_em"] = base + timedelta(days=6, hours=5)
        Pedido.objects.filter(pk=pedido.pk).update(**campos)
