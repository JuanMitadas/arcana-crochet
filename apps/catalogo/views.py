from django.contrib.postgres.search import TrigramSimilarity
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.avaliacoes.models import Avaliacao
from apps.core import precos
from apps.pedidos import frete as modulo_frete

from .models import Categoria, Produto, ProdutoFoto, ProdutoVariacao

POR_PAGINA = 24

ORDENACOES = {
    "relevancia": ("Mais relevantes", ["-destaque", "-unidades_vendidas", "-publicado_em"]),
    "mais_vendidos": ("Mais vendidos", ["-unidades_vendidas", "-publicado_em"]),
    "menor_preco": ("Menor preço", ["preco_efetivo", "nome"]),
    "maior_preco": ("Maior preço", ["-preco_efetivo", "nome"]),
    "novidades": ("Novidades", ["-publicado_em", "-criado_em"]),
    "avaliados": ("Mais bem avaliados", ["-nota_media", "-total_avaliacoes"]),
}

FAIXAS_PRECO = [
    ("Até R$ 50", "", "50"),
    ("R$ 50 a R$ 100", "50", "100"),
    ("R$ 100 a R$ 200", "100", "200"),
    ("Acima de R$ 200", "200", ""),
]


def vitrine_qs():
    """Produtos visíveis com fotos, variações ativas e métricas para os cards."""
    return (
        Produto.objects.visiveis()
        .com_metricas()
        .select_related("categoria")
        .prefetch_related(
            Prefetch("fotos", queryset=ProdutoFoto.objects.order_by("ordem")),
            Prefetch("variacoes", queryset=ProdutoVariacao.objects.filter(ativa=True)),
        )
    )


# --- Página inicial --------------------------------------------------------


def home(request):
    base = vitrine_qs().filter(status=Produto.Status.ATIVO)
    contexto = {
        "destaques": base.filter(destaque=True).order_by("-publicado_em")[:12],
        "ofertas": base.filter(preco_promocional_centavos__isnull=False).order_by("preco_efetivo")[
            :12
        ],
        "novidades": base.order_by("-publicado_em", "-criado_em")[:12],
        "mais_vendidos": base.filter(unidades_vendidas__gt=0).order_by("-unidades_vendidas")[:12],
        "categorias_home": Categoria.objects.filter(ativa=True, pai__isnull=True),
    }
    return render(request, "catalogo/home.html", contexto)


# --- Listagem: categoria, busca e todas as peças ---------------------------


def _reais_para_centavos(valor: str):
    try:
        return int(round(float(valor.replace(",", ".")) * 100)) if valor else None
    except ValueError:
        return None


# Palavras que toda peça tem: não filtram nada, então são ignoradas na busca.
PALAVRAS_VAZIAS = {"croche", "crochê", "crochet", "de", "da", "do", "das", "dos", "em",
                   "para", "com", "e", "a", "o", "feito", "feita", "mao", "mão"}  # fmt: skip


def _buscar(produtos, termo: str):
    palavras = [p for p in termo.lower().split() if p not in PALAVRAS_VAZIAS]
    for palavra in palavras:
        produtos = produtos.filter(
            Q(nome__unaccent__icontains=palavra)
            | Q(descricao__unaccent__icontains=palavra)
            | Q(material__unaccent__icontains=palavra)
            | Q(categoria__nome__unaccent__icontains=palavra)
            | Q(variacoes__cor__unaccent__icontains=palavra)
        )
    return produtos.distinct()


def _facetas(produtos):
    """Valores disponíveis para os filtros, contados sobre o resultado sem esses filtros."""
    variacoes = ProdutoVariacao.objects.filter(ativa=True, produto__in=produtos.values("pk"))
    cores = (
        variacoes.exclude(cor="")
        .values("cor", "cor_hex")
        .annotate(total=Count("produto", distinct=True))
        .order_by("cor")
    )
    # Uma linha por cor, mesmo que duas variações tenham hex diferente.
    vistas, lista_cores = set(), []
    for cor in cores:
        if cor["cor"].lower() not in vistas:
            vistas.add(cor["cor"].lower())
            lista_cores.append(cor)
    tamanhos = (
        variacoes.exclude(tamanho="")
        .values("tamanho")
        .annotate(total=Count("produto", distinct=True))
        .order_by("tamanho")
    )
    materiais = (
        produtos.exclude(material="")
        .values("material")
        .annotate(total=Count("pk", distinct=True))
        .order_by(Lower("material"))
    )
    disponibilidade = (
        produtos.values("disponibilidade")
        .annotate(total=Count("pk", distinct=True))
        .order_by("disponibilidade")
    )
    return {
        "cores": lista_cores,
        "tamanhos": list(tamanhos),
        "materiais": list(materiais),
        "disponibilidade": [
            {**d, "nome": Produto.Disponibilidade(d["disponibilidade"]).label}
            for d in disponibilidade
        ],
        "em_promocao": produtos.filter(preco_promocional_centavos__isnull=False).count(),
    }


def listagem(request, slug=None):
    categoria = None
    produtos = vitrine_qs()
    if slug:
        categoria = get_object_or_404(
            Categoria.objects.select_related("pai").prefetch_related("filhas"),
            slug=slug,
            ativa=True,
        )
        produtos = produtos.filter(Q(categoria=categoria) | Q(categoria__pai=categoria))

    termo = request.GET.get("q", "").strip()[:80]
    if termo:
        produtos = _buscar(produtos, termo)

    base = produtos  # antes dos filtros, para montar as facetas
    get = request.GET
    filtros = {
        "cores": [c for c in get.getlist("cor") if c],
        "tamanhos": [t for t in get.getlist("tamanho") if t],
        "materiais": [m for m in get.getlist("material") if m],
        "disponibilidade": get.get("disponibilidade", ""),
        "promocao": get.get("promocao") == "1",
        "preco_min": get.get("preco_min", "").strip(),
        "preco_max": get.get("preco_max", "").strip(),
    }
    if filtros["cores"]:
        consulta = Q()
        for cor in filtros["cores"]:
            consulta |= Q(variacoes__cor__iexact=cor, variacoes__ativa=True)
        produtos = produtos.filter(consulta)
    if filtros["tamanhos"]:
        produtos = produtos.filter(
            variacoes__tamanho__in=filtros["tamanhos"], variacoes__ativa=True
        )
    if filtros["materiais"]:
        produtos = produtos.filter(material__in=filtros["materiais"])
    if filtros["disponibilidade"] in Produto.Disponibilidade.values:
        produtos = produtos.filter(disponibilidade=filtros["disponibilidade"])
    if filtros["promocao"]:
        produtos = produtos.filter(preco_promocional_centavos__isnull=False)
    minimo = _reais_para_centavos(filtros["preco_min"])
    maximo = _reais_para_centavos(filtros["preco_max"])
    if minimo is not None:
        produtos = produtos.filter(preco_efetivo__gte=minimo)
    if maximo is not None:
        produtos = produtos.filter(preco_efetivo__lte=maximo)
    produtos = produtos.distinct()

    ordem = get.get("ordem", "relevancia")
    if ordem not in ORDENACOES:
        ordem = "relevancia"
    produtos = produtos.order_by(*ORDENACOES[ordem][1], "pk")

    pagina = Paginator(produtos, POR_PAGINA).get_page(get.get("page"))

    sugestoes = []
    if termo and not pagina.paginator.count:
        sugestoes = (
            vitrine_qs()
            .annotate(similaridade=TrigramSimilarity("nome", termo))
            .filter(similaridade__gt=0.15)
            .order_by("-similaridade")[:4]
        )

    chips = _chips(filtros, request)
    contexto = {
        "categoria": categoria,
        "termo": termo,
        "pagina": pagina,
        "produtos": pagina.object_list,
        "total": pagina.paginator.count,
        "facetas": _facetas(base),
        "filtros": filtros,
        "chips": chips,
        "ordem": ordem,
        "ordenacoes": [(chave, nome) for chave, (nome, _) in ORDENACOES.items()],
        "faixas_preco": FAIXAS_PRECO,
        "sugestoes": sugestoes,
    }
    if request.htmx and request.htmx.target == "resultados":
        return render(request, "catalogo/listagem.html#resultados", contexto)
    return render(request, "catalogo/listagem.html", contexto)


def _chips(filtros, request):
    """Filtros ativos como etiquetas removíveis."""
    chips = []

    def sem(chave, valor=None):
        params = request.GET.copy()
        params.pop("page", None)
        if valor is None:
            params.pop(chave, None)
        else:
            params.setlist(chave, [v for v in params.getlist(chave) if v != valor])
        texto = params.urlencode()
        return f"?{texto}" if texto else request.path

    for cor in filtros["cores"]:
        chips.append((f"Cor: {cor}", sem("cor", cor)))
    for tamanho in filtros["tamanhos"]:
        chips.append((f"Tamanho: {tamanho}", sem("tamanho", tamanho)))
    for material in filtros["materiais"]:
        chips.append((material, sem("material", material)))
    if filtros["disponibilidade"] in Produto.Disponibilidade.values:
        chips.append(
            (Produto.Disponibilidade(filtros["disponibilidade"]).label, sem("disponibilidade"))
        )
    if filtros["promocao"]:
        chips.append(("Em promoção", sem("promocao")))
    if filtros["preco_min"] or filtros["preco_max"]:
        params = request.GET.copy()
        params.pop("preco_min", None)
        params.pop("preco_max", None)
        params.pop("page", None)
        texto = params.urlencode()
        rotulo = "Preço: " + (
            f"R$ {filtros['preco_min'] or '0'} a R$ {filtros['preco_max']}"
            if filtros["preco_max"]
            else f"a partir de R$ {filtros['preco_min']}"
        )
        chips.append((rotulo, f"?{texto}" if texto else request.path))
    return chips


# --- Página do produto -----------------------------------------------------


def produto_detalhe(request, slug):
    produto = get_object_or_404(
        vitrine_qs().prefetch_related("especificacoes").select_related("categoria__pai"),
        slug=slug,
    )
    variacoes = list(produto.variacoes.all())
    avaliacoes = (
        Avaliacao.objects.filter(produto=produto, status=Avaliacao.Status.PUBLICADA)
        .select_related("autor")
        .order_by("-criado_em")
    )
    contagem = dict(avaliacoes.values_list("nota").annotate(total=Count("pk")).order_by())
    total_avaliacoes = sum(contagem.values())
    distribuicao = [{"nota": nota, "total": contagem.get(nota, 0)} for nota in range(5, 0, -1)]
    relacionados = (
        vitrine_qs()
        .filter(categoria=produto.categoria, status=Produto.Status.ATIVO)
        .exclude(pk=produto.pk)
        .order_by("-destaque", "-unidades_vendidas")[:10]
    )

    dados_variacoes = [
        {
            "id": str(v.pk),
            "cor": v.cor,
            "cor_hex": v.cor_hex,
            "tamanho": v.tamanho,
            "preco": v.preco_centavos,
            "disponivel": v.disponivel,
        }
        for v in variacoes
    ]
    cores = []
    for v in variacoes:
        if v.cor and v.cor not in [c["nome"] for c in cores]:
            cores.append({"nome": v.cor, "hex": v.cor_hex})
    tamanhos = list(dict.fromkeys(v.tamanho for v in variacoes if v.tamanho))
    sob_encomenda = produto.disponibilidade == Produto.Disponibilidade.SOB_ENCOMENDA
    primeira = next((v for v in variacoes if sob_encomenda or v.disponivel > 0), None) or (
        variacoes[0] if variacoes else None
    )

    cep = (request.session.get("sacola") or {}).get("cep", "")
    frete_opcoes = []
    if modulo_frete.cep_valido(cep):
        frete_opcoes = modulo_frete.cotar(
            cep, produto.peso_g, produto.preco_atual_centavos, produto.prazo_producao_dias or 0
        )

    contexto = {
        "produto": produto,
        "variacoes": variacoes,
        "variacao_inicial": primeira,
        "dados_variacoes": dados_variacoes,
        "cores": cores,
        "tamanhos": tamanhos,
        "sob_encomenda": sob_encomenda,
        "comprar_disponivel": primeira is not None and (sob_encomenda or primeira.disponivel > 0),
        "opcoes_parcelas": precos.opcoes_parcelamento(produto.preco_atual_centavos),
        "avaliacoes": avaliacoes[:10],
        "total_avaliacoes": total_avaliacoes,
        "distribuicao": distribuicao,
        "nota_media": produto.nota_media or 0,
        "relacionados": relacionados,
        "cep": cep,
        "frete_opcoes": frete_opcoes,
        "frete_regiao": modulo_frete.regiao(cep) if frete_opcoes else "",
    }
    return render(request, "catalogo/produto.html", contexto)


@require_POST
def produto_frete(request, slug):
    """Cálculo rápido de frete na página do produto (HTMX)."""
    produto = get_object_or_404(Produto.objects.visiveis(), slug=slug)
    cep = modulo_frete.limpar_cep(request.POST.get("cep", ""))
    contexto = {"cep": cep, "erro": "", "opcoes": []}
    try:
        quantidade = max(1, min(int(request.POST.get("quantidade", 1)), 10))
    except ValueError:
        quantidade = 1
    try:
        contexto["opcoes"] = modulo_frete.cotar(
            cep,
            produto.peso_g * quantidade,
            produto.preco_atual_centavos * quantidade,
            produto.prazo_producao_dias or 0,
        )
        contexto["regiao"] = modulo_frete.regiao(cep)
        sacola = request.session.get("sacola") or {}
        request.session["sacola"] = {**sacola, "cep": cep}
    except ValueError as erro:
        contexto["erro"] = str(erro)
    contexto["sob_encomenda"] = produto.disponibilidade == Produto.Disponibilidade.SOB_ENCOMENDA
    if not request.htmx:
        return redirect(f"{produto.get_absolute_url()}#titulo-frete")
    return render(request, "catalogo/_frete.html", contexto)
