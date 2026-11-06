from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.avaliacoes.models import Avaliacao
from apps.catalogo.models import Produto, ProdutoFoto, ProdutoVariacao
from apps.contas.models import Endereco
from apps.core import precos

from . import servicos
from .carrinho import Carrinho
from .forms import AvaliacaoForm, EnderecoForm
from .frete import cep_valido, limpar_cep
from .models import Pedido, PedidoItem

CHAVE_CHECKOUT = "checkout"


# --- Bag -------------------------------------------------------------------


def _render_sacola(request, carrinho):
    contexto = {"carrinho": carrinho, "sacola_quantidade": carrinho.quantidade_total}
    if request.htmx:
        return render(request, "pedidos/sacola.html#conteudo", contexto)
    return render(request, "pedidos/sacola.html", contexto)


def sacola(request):
    carrinho = Carrinho(request)
    carrinho.itens  # noqa: B018 — loads the items and adjusts out-of-stock ones before rendering
    if carrinho.ajustado:
        messages.warning(
            request, "Ajustamos a quantidade de alguns itens conforme o estoque disponível."
        )
    return _render_sacola(request, carrinho)


@require_POST
def adicionar(request):
    variacao = get_object_or_404(
        ProdutoVariacao.objects.select_related("produto"),
        pk=request.POST.get("variacao"),
        ativa=True,
        produto__status__in=[Produto.Status.ATIVO, Produto.Status.ESGOTADO],
    )
    try:
        quantidade = max(1, int(request.POST.get("quantidade", 1)))
    except ValueError:
        quantidade = 1
    carrinho = Carrinho(request)
    antes = carrinho._itens.get(str(variacao.pk), 0)
    final = carrinho.adicionar(variacao, quantidade)

    if final <= antes:
        messages.warning(request, "Não há mais unidades disponíveis desta peça.")
        return redirect(variacao.produto)
    if final < antes + quantidade:
        messages.info(request, f"Só temos {final} unidade(s) desta peça; ajustamos a quantidade.")
    if request.POST.get("acao") == "comprar":
        return redirect("pedidos:checkout")
    messages.success(request, f"{variacao.produto.nome} foi para a sacola.")
    return redirect("pedidos:sacola")


@require_POST
def atualizar_item(request, variacao_id):
    carrinho = Carrinho(request)
    variacao = ProdutoVariacao.objects.select_related("produto").filter(pk=variacao_id).first()
    if variacao is None or request.POST.get("acao") == "remover":
        carrinho.remover(variacao_id)
    else:
        try:
            quantidade = int(request.POST.get("quantidade", 1))
        except ValueError:
            quantidade = 1
        if request.POST.get("acao") == "mais":
            quantidade += 1
        elif request.POST.get("acao") == "menos":
            quantidade -= 1
        carrinho.definir(variacao, quantidade)
    return _render_sacola(request, carrinho) if request.htmx else redirect("pedidos:sacola")


@require_POST
def aplicar_cupom(request):
    carrinho = Carrinho(request)
    if request.POST.get("acao") == "remover":
        carrinho.cupom_codigo = ""
    else:
        carrinho.cupom_codigo = request.POST.get("cupom", "").strip().upper()[:30]
    carrinho.salvar()
    return _render_sacola(request, carrinho) if request.htmx else redirect("pedidos:sacola")


@require_POST
def calcular_frete(request):
    carrinho = Carrinho(request)
    if "cep" in request.POST:
        carrinho.cep = limpar_cep(request.POST["cep"])
    if request.POST.get("frete") in ("pac", "sedex"):
        carrinho.frete_codigo = request.POST["frete"]
    carrinho.salvar()
    if request.POST.get("voltar") == "entrega":
        return redirect("pedidos:checkout_entrega")
    return _render_sacola(request, carrinho) if request.htmx else redirect("pedidos:sacola")


# --- Checkout --------------------------------------------------------------


def _estado(request) -> dict:
    return request.session.get(CHAVE_CHECKOUT) or {}


def _guardar_estado(request, **dados):
    request.session[CHAVE_CHECKOUT] = {**_estado(request), **dados}


def _exigir_sacola(request):
    carrinho = Carrinho(request)
    if not carrinho.itens:
        messages.info(request, "Sua sacola está vazia. Escolha uma peça para continuar.")
        return None
    return carrinho


def _contexto_checkout(carrinho, etapa, **extra):
    etapas = [
        ("identificacao", "Identificação"),
        ("entrega", "Entrega"),
        ("pagamento", "Pagamento"),
        ("revisao", "Revisão"),
    ]
    indice = [chave for chave, _ in etapas].index(etapa)
    return {
        "carrinho": carrinho,
        "etapa": etapa,
        "etapas": [
            {
                "chave": chave,
                "nome": nome,
                "numero": n + 1,
                "feita": n < indice,
                "atual": n == indice,
            }
            for n, (chave, nome) in enumerate(etapas)
        ],
        **extra,
    }


def checkout(request):
    if not Carrinho(request).itens:
        return redirect("pedidos:sacola")
    if request.user.is_authenticated:
        return redirect("pedidos:checkout_entrega")
    return redirect("pedidos:checkout_identificacao")


def checkout_identificacao(request):
    if request.user.is_authenticated:
        return redirect("pedidos:checkout_entrega")
    carrinho = _exigir_sacola(request)
    if carrinho is None:
        return redirect("pedidos:sacola")
    from allauth.account.forms import LoginForm

    proximo = reverse("pedidos:checkout_entrega")
    return render(
        request,
        "pedidos/checkout/identificacao.html",
        _contexto_checkout(carrinho, "identificacao", form=LoginForm(), proximo=proximo),
    )


@login_required
def checkout_entrega(request):
    carrinho = _exigir_sacola(request)
    if carrinho is None:
        return redirect("pedidos:sacola")
    enderecos = list(request.user.enderecos.all())
    estado = _estado(request)
    selecionado = next((e for e in enderecos if str(e.pk) == estado.get("endereco")), None) or next(
        iter(enderecos), None
    )
    novo = request.POST.get("endereco") == "novo" or not enderecos
    form = (
        EnderecoForm(request.POST or None, prefix="novo") if novo else EnderecoForm(prefix="novo")
    )

    if request.method == "POST":
        if novo:
            if form.is_valid():
                endereco = form.save(commit=False)
                endereco.usuario = request.user
                if not enderecos:
                    endereco.padrao = True
                endereco.save()
                selecionado = endereco
            else:
                selecionado = None
        else:
            selecionado = next(
                (e for e in enderecos if str(e.pk) == request.POST.get("endereco")), None
            )
        if selecionado:
            carrinho.cep = selecionado.cep
            if request.POST.get("frete") in ("pac", "sedex"):
                carrinho.frete_codigo = request.POST["frete"]
            carrinho.salvar()
            _guardar_estado(request, endereco=str(selecionado.pk))
            if request.POST.get("acao") == "atualizar":
                return redirect("pedidos:checkout_entrega")
            return redirect("pedidos:checkout_pagamento")
        if not novo:
            messages.error(request, "Escolha um endereço de entrega.")
    elif selecionado and carrinho.cep != selecionado.cep:
        carrinho.cep = selecionado.cep
        carrinho.salvar()

    return render(
        request,
        "pedidos/checkout/entrega.html",
        _contexto_checkout(
            carrinho,
            "entrega",
            enderecos=enderecos,
            selecionado=selecionado,
            form=form,
            mostrar_form=novo,
        ),
    )


def _endereco_escolhido(request):
    pk = _estado(request).get("endereco")
    return request.user.enderecos.filter(pk=pk).first() if pk else None


@login_required
def checkout_pagamento(request):
    carrinho = _exigir_sacola(request)
    if carrinho is None:
        return redirect("pedidos:sacola")
    endereco = _endereco_escolhido(request)
    if endereco is None or not cep_valido(carrinho.cep):
        return redirect("pedidos:checkout_entrega")

    estado = _estado(request)
    opcoes = precos.opcoes_parcelamento(carrinho.total_centavos)
    if request.method == "POST":
        metodo = request.POST.get("metodo")
        if metodo in Pedido.Metodo.values:
            try:
                parcelas = int(request.POST.get("parcelas", 1))
            except ValueError:
                parcelas = 1
            parcelas = max(1, min(parcelas, len(opcoes))) if metodo == "cartao" else 1
            _guardar_estado(request, metodo=metodo, parcelas=parcelas)
            return redirect("pedidos:checkout_revisao")
        messages.error(request, "Escolha uma forma de pagamento.")

    return render(
        request,
        "pedidos/checkout/pagamento.html",
        _contexto_checkout(
            carrinho,
            "pagamento",
            endereco=endereco,
            metodo=estado.get("metodo", "pix"),
            parcelas=estado.get("parcelas", 1),
            opcoes_parcelas=opcoes,
        ),
    )


@login_required
def checkout_revisao(request):
    carrinho = _exigir_sacola(request)
    if carrinho is None:
        return redirect("pedidos:sacola")
    endereco = _endereco_escolhido(request)
    estado = _estado(request)
    if endereco is None or not cep_valido(carrinho.cep):
        return redirect("pedidos:checkout_entrega")
    if estado.get("metodo") not in Pedido.Metodo.values:
        return redirect("pedidos:checkout_pagamento")

    metodo, parcelas = estado["metodo"], estado.get("parcelas", 1)
    if request.method == "POST":
        if not request.POST.get("aceite"):
            messages.error(request, "Para continuar, aceite os termos e a política de trocas.")
        else:
            try:
                pedido = servicos.criar_pedido(
                    request.user,
                    carrinho,
                    endereco,
                    metodo,
                    parcelas,
                    observacao=request.POST.get("observacao", "")[:300],
                )
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
                return redirect("pedidos:sacola")
            request.session.pop(CHAVE_CHECKOUT, None)
            return redirect(f"{pedido.get_absolute_url()}?novo=1")

    total = carrinho.total_pix_centavos if metodo == "pix" else carrinho.total_centavos
    return render(
        request,
        "pedidos/checkout/revisao.html",
        _contexto_checkout(
            carrinho,
            "revisao",
            endereco=endereco,
            metodo=metodo,
            metodo_nome=Pedido.Metodo(metodo).label,
            parcelas=parcelas,
            total=total,
            valor_parcela=precos.opcoes_parcelamento(carrinho.total_centavos)[parcelas - 1]
            if metodo == "cartao"
            else None,
        ),
    )


# --- My account ------------------------------------------------------------


def _itens_com_fotos():
    return Prefetch(
        "itens",
        queryset=PedidoItem.objects.select_related("produto").prefetch_related(
            Prefetch("produto__fotos", queryset=ProdutoFoto.objects.order_by("ordem"))
        ),
    )


@login_required
def pedidos_lista(request):
    pedidos = request.user.pedidos.prefetch_related(_itens_com_fotos())
    filtro = request.GET.get("status", "")
    if filtro == "andamento":
        pedidos = pedidos.exclude(status__in=[Pedido.Status.ENTREGUE, Pedido.Status.CANCELADO])
    elif filtro in ("entregue", "cancelado"):
        pedidos = pedidos.filter(status=filtro)
    return render(
        request,
        "pedidos/conta/pedidos.html",
        {"pedidos": pedidos, "filtro": filtro, "secao": "pedidos"},
    )


@login_required
def pedido_detalhe(request, codigo):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related(_itens_com_fotos()), codigo=codigo, cliente=request.user
    )
    avaliados = set(Avaliacao.objects.filter(item__pedido=pedido).values_list("item_id", flat=True))
    return render(
        request,
        "pedidos/conta/pedido.html",
        {
            "pedido": pedido,
            "novo": request.GET.get("novo") == "1",
            "avaliados": avaliados,
            "pode_simular": settings.DEBUG,
            "secao": "pedidos",
        },
    )


@login_required
@require_POST
def simular_pagamento(request, codigo):
    """Development only: approve the payment without Asaas, to test the flow."""
    if not settings.DEBUG:
        raise Http404
    pedido = get_object_or_404(Pedido, codigo=codigo, cliente=request.user)
    try:
        servicos.marcar_pago(pedido)
        messages.success(request, "Pagamento aprovado (simulação).")
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
    return redirect(pedido)


@login_required
def enderecos(request):
    form = EnderecoForm(request.POST or None)
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao in ("remover", "principal"):
            endereco = get_object_or_404(Endereco, pk=request.POST.get("id"), usuario=request.user)
            if acao == "remover":
                endereco.delete()
                messages.success(request, "Endereço removido.")
            else:
                request.user.enderecos.update(padrao=False)
                endereco.padrao = True
                endereco.save(update_fields=["padrao"])
            return redirect("pedidos:enderecos")
        if form.is_valid():
            endereco = form.save(commit=False)
            endereco.usuario = request.user
            if endereco.padrao or not request.user.enderecos.exists():
                request.user.enderecos.update(padrao=False)
                endereco.padrao = True
            endereco.save()
            messages.success(request, "Endereço salvo.")
            return redirect("pedidos:enderecos")
    return render(
        request,
        "pedidos/conta/enderecos.html",
        {
            "enderecos": request.user.enderecos.all(),
            "form": form,
            "mostrar_form": request.method == "POST" or request.GET.get("novo") == "1",
            "secao": "enderecos",
        },
    )


@login_required
def avaliar(request, item_id):
    item = get_object_or_404(
        PedidoItem.objects.select_related("pedido", "produto"),
        pk=item_id,
        pedido__cliente=request.user,
    )
    if not item.pedido.pode_avaliar:
        raise PermissionDenied("Você poderá avaliar quando receber a peça.")
    if Avaliacao.objects.filter(item=item).exists():
        messages.info(request, "Você já avaliou esta peça. Obrigada!")
        return redirect(item.pedido)
    form = AvaliacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        avaliacao = form.save(commit=False)
        avaliacao.item = item
        avaliacao.produto = item.produto
        avaliacao.autor = request.user
        avaliacao.save()
        messages.success(
            request, "Obrigada pela avaliação! Ela aparece na página da peça depois de revisada."
        )
        return redirect(item.pedido)
    return render(
        request,
        "pedidos/conta/avaliar.html",
        {"item": item, "form": form, "secao": "pedidos"},
    )
