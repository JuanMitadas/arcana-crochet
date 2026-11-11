"""Management panel for the store team: the daily tasks, in the store's own look.

Only team members (``is_staff``) get in; each action also checks the Django
permission behind it, so an attendant sees what their group allows. Everything that
changes orders or stock goes through the same services as the rest of the store.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.avaliacoes.models import Avaliacao
from apps.catalogo.estoque import registrar_movimentacao
from apps.catalogo.models import MovimentacaoEstoque, Produto, ProdutoFoto, ProdutoVariacao
from apps.core.texto import normalizar
from apps.pedidos import servicos
from apps.pedidos.models import Pedido

from .forms import (
    ETAPAS_PEDIDO,
    CancelarForm,
    EnvioForm,
    EspecificacaoFormSet,
    EstoqueForm,
    FotosForm,
    ProdutoForm,
    RespostaForm,
    VariacaoFormSet,
)

ESTOQUE_BAIXO = 1
MUDOU_DE_ETAPA = "O pedido mudou de etapa. Confira e tente de novo."


def equipe(permissao: str | None = None):
    """Team members only; with ``permissao``, also that Django permission."""

    def decorador(view):
        @wraps(view)
        def envolvida(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.is_staff:
                raise PermissionDenied
            if permissao and not request.user.has_perm(permissao):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return envolvida

    return decorador


def _estoque_baixo():
    return (
        ProdutoVariacao.objects.filter(
            ativa=True,
            produto__status__in=[Produto.Status.ATIVO, Produto.Status.ESGOTADO],
            produto__disponibilidade=Produto.Disponibilidade.PRONTA_ENTREGA,
        )
        .annotate(livre=F("estoque") - F("estoque_reservado"))
        .filter(livre__lte=ESTOQUE_BAIXO)
        .select_related("produto")
        .order_by("livre", "produto__nome")
    )


# --- Home ---------------------------------------------------------------------


@equipe()
def inicio(request):
    contagem = Pedido.objects.aggregate(
        pagar=Count("pk", filter=Q(status=Pedido.Status.AGUARDANDO_PAGAMENTO)),
        separar=Count("pk", filter=Q(status=Pedido.Status.PAGO)),
        enviar=Count("pk", filter=Q(status=Pedido.Status.EM_SEPARACAO)),
        caminho=Count("pk", filter=Q(status=Pedido.Status.ENVIADO)),
    )
    inicio_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    vendas = Pedido.objects.filter(status__in=Pedido.STATUS_PAGOS, pago_em__gte=inicio_mes)
    resumo_mes = vendas.aggregate(total=Sum("total_centavos"), pedidos=Count("pk"))
    return render(
        request,
        "gestao/inicio.html",
        {
            "contagem": contagem,
            "resumo_mes": resumo_mes,
            "inicio_mes": inicio_mes,
            "avaliacoes_pendentes": Avaliacao.objects.filter(
                status=Avaliacao.Status.PENDENTE
            ).count(),
            "estoque_baixo": _estoque_baixo()[:8],
            "pix_pendentes": Pedido.objects.filter(status=Pedido.Status.AGUARDANDO_PAGAMENTO)
            .select_related("cliente")
            .order_by("criado_em")[:5],
            "secao": "inicio",
        },
    )


# --- Orders -------------------------------------------------------------------


@equipe("pedidos.view_pedido")
def pedidos(request):
    etapa = request.GET.get("etapa", "pagar")
    if etapa not in ETAPAS_PEDIDO and etapa != "todos":
        etapa = "pagar"
    lista = Pedido.objects.select_related("cliente").prefetch_related("itens")
    if etapa != "todos":
        lista = lista.filter(status__in=ETAPAS_PEDIDO[etapa][1])
    termo = request.GET.get("q", "").strip()
    if termo:
        lista = lista.filter(
            Q(codigo__icontains=termo)
            | Q(cliente__email__icontains=termo)
            | Q(cliente__nome_completo__icontains=termo)
        )
    # Oldest first while there is something to do; newest first otherwise.
    ordem = "criado_em" if etapa in ("pagar", "separar", "enviar") else "-criado_em"
    pagina = Paginator(lista.order_by(ordem), 20).get_page(request.GET.get("pagina"))
    contagem = dict(
        Pedido.objects.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
    )
    etapas = [
        (chave, nome, sum(contagem.get(s, 0) for s in status))
        for chave, (nome, status) in ETAPAS_PEDIDO.items()
    ]
    return render(
        request,
        "gestao/pedidos.html",
        {
            "pagina": pagina,
            "etapa": etapa,
            "etapas": etapas,
            "termo": termo,
            "envio_form": EnvioForm(),
            "secao": "pedidos",
        },
    )


@equipe("pedidos.view_pedido")
def pedido(request, codigo):
    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente", "cupom").prefetch_related("itens__produto"),
        codigo=codigo,
    )
    return render(
        request,
        "gestao/pedido.html",
        {
            "pedido": pedido,
            "envio_form": EnvioForm(initial={"codigo_rastreio": pedido.codigo_rastreio}),
            "cancelar_form": CancelarForm(),
            "secao": "pedidos",
        },
    )


ACOES_PEDIDO = {
    "confirmar-pix": "Pagamento do pedido {codigo} confirmado. As peças viraram venda.",
    "separar": "Pedido {codigo} em separação.",
    "enviar": "Pedido {codigo} marcado como enviado.",
    "entregar": "Pedido {codigo} marcado como entregue.",
    "cancelar": "Pedido {codigo} cancelado e as peças voltaram para a loja.",
}


@require_POST
@equipe("pedidos.change_pedido")
def acao_pedido(request, codigo, acao):
    pedido = get_object_or_404(Pedido, codigo=codigo)
    if acao not in ACOES_PEDIDO:
        raise PermissionDenied
    try:
        if acao == "confirmar-pix":
            servicos.marcar_pago(pedido)
        elif acao in ("separar", "entregar"):
            esperado = Pedido.Status.PAGO if acao == "separar" else Pedido.Status.ENVIADO
            if pedido.status != esperado:
                raise servicos.TransicaoInvalida(
                    "O pedido mudou de etapa. Confira e tente de novo."
                )
            servicos.avancar(pedido)
        elif acao == "enviar":
            form = EnvioForm(request.POST)
            if not form.is_valid():
                raise servicos.TransicaoInvalida("Informe o código de rastreio.")
            if pedido.status != Pedido.Status.EM_SEPARACAO:
                raise servicos.TransicaoInvalida(
                    "O pedido mudou de etapa. Confira e tente de novo."
                )
            servicos.avancar(pedido, **form.cleaned_data)
        else:
            form = CancelarForm(request.POST)
            form.is_valid()
            servicos.cancelar(pedido, motivo=form.cleaned_data.get("motivo", ""))
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    else:
        messages.success(request, ACOES_PEDIDO[acao].format(codigo=pedido.codigo))
    destino = request.POST.get("voltar", "")
    if destino.startswith("/gestao/"):
        return redirect(destino)
    return redirect("gestao:pedido", codigo=pedido.codigo)


# --- Pieces -------------------------------------------------------------------


@equipe("catalogo.view_produto")
def pecas(request):
    lista = (
        Produto.objects.select_related("categoria")
        .prefetch_related("fotos")
        .annotate(
            estoque_total=Sum("variacoes__estoque", filter=Q(variacoes__ativa=True)),
            reservado_total=Sum("variacoes__estoque_reservado", filter=Q(variacoes__ativa=True)),
        )
        .order_by("-atualizado_em")
    )
    status = request.GET.get("status", "")
    if status in Produto.Status.values:
        lista = lista.filter(status=status)
    termo = request.GET.get("q", "").strip()
    if termo:
        for palavra in normalizar(termo).split():
            lista = lista.filter(busca__contains=palavra)
    pagina = Paginator(lista, 24).get_page(request.GET.get("pagina"))
    return render(
        request,
        "gestao/pecas.html",
        {
            "pagina": pagina,
            "status": status,
            "termo": termo,
            "status_opcoes": Produto.Status.choices,
            "secao": "pecas",
        },
    )


@equipe("catalogo.view_produto")
def peca_form(request, pk=None):
    produto = get_object_or_404(Produto, pk=pk) if pk else Produto()
    pode_editar = request.user.has_perm("catalogo.change_produto" if pk else "catalogo.add_produto")
    if request.method == "POST":
        if not pode_editar:
            raise PermissionDenied
        form = ProdutoForm(request.POST, instance=produto)
        variacoes = VariacaoFormSet(request.POST, instance=produto, prefix="variacoes")
        especificacoes = EspecificacaoFormSet(request.POST, instance=produto, prefix="ficha")
        if form.is_valid() and variacoes.is_valid() and especificacoes.is_valid():
            _salvar_peca(request, form, variacoes, especificacoes)
            messages.success(request, f"Peça “{form.instance.nome}” salva.")
            return redirect("gestao:peca", pk=form.instance.pk)
        messages.error(request, "Confira os campos destacados.")
    else:
        form = ProdutoForm(instance=produto)
        variacoes = VariacaoFormSet(instance=produto, prefix="variacoes")
        especificacoes = EspecificacaoFormSet(instance=produto, prefix="ficha")

    contexto = {
        "produto": produto,
        "form": form,
        "variacoes": variacoes,
        "especificacoes": especificacoes,
        "pode_editar": pode_editar,
        "nova": produto._state.adding,
        "secao": "pecas",
    }
    if not contexto["nova"]:
        contexto |= {
            "fotos": produto.fotos.select_related("variacao").order_by("ordem"),
            "fotos_form": FotosForm(produto=produto),
            "estoque_variacoes": produto.variacoes.order_by("cor", "tamanho"),
            "movimentacoes": MovimentacaoEstoque.objects.filter(variacao__produto=produto)
            .select_related("variacao", "autor")
            .order_by("-criado_em")[:10],
            "pode_estoque": request.user.has_perm("catalogo.add_movimentacaoestoque"),
        }
    return render(request, "gestao/peca_form.html", contexto)


def _salvar_peca(request, form, variacoes, especificacoes):
    # One step at a time instead of one big transaction: on Aurora DSQL a long
    # transaction is more likely to conflict, and each step is safe on its own.
    produto = form.save()
    variacoes.instance = produto
    for variacao_form in variacoes.forms:
        if not variacao_form.has_changed():
            continue
        if not variacao_form.instance._state.adding:
            variacao_form.save()
            continue
        variacao = variacoes.save_new(variacao_form)
        inicial = variacao_form.cleaned_data.get("estoque_inicial") or 0
        if inicial:
            registrar_movimentacao(
                variacao,
                MovimentacaoEstoque.Tipo.ENTRADA_PRODUCAO,
                inicial,
                autor=request.user,
                motivo="Estoque inicial",
            )
    especificacoes.instance = produto
    especificacoes.save()
    produto.atualizar_busca()


@require_POST
@equipe("catalogo.add_movimentacaoestoque")
def estoque(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    form = EstoqueForm(request.POST)
    if form.is_valid():
        variacao = get_object_or_404(produto.variacoes, pk=form.cleaned_data["variacao"])
        quantidade = form.cleaned_data["quantidade"]
        tipo = (
            MovimentacaoEstoque.Tipo.ENTRADA_PRODUCAO
            if quantidade > 0
            else MovimentacaoEstoque.Tipo.AJUSTE
        )
        try:
            registrar_movimentacao(
                variacao,
                tipo,
                quantidade,
                autor=request.user,
                motivo=form.cleaned_data["motivo"],
            )
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        else:
            messages.success(request, f"Estoque de {variacao} atualizado.")
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect(f"{produto_url(produto)}#estoque")


def produto_url(produto):
    return reverse("gestao:peca", kwargs={"pk": produto.pk})


@require_POST
@equipe("catalogo.change_produto")
def fotos(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    form = FotosForm(request.POST, request.FILES, produto=produto)
    if form.is_valid():
        enviadas = form.salvar()
        plural = "s" if enviadas > 1 else ""
        messages.success(request, f"{enviadas} foto{plural} adicionada{plural}.")
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect(f"{produto_url(produto)}#fotos")


@require_POST
@equipe("catalogo.change_produto")
def foto_acao(request, pk, foto_pk, acao):
    produto = get_object_or_404(Produto, pk=pk)
    foto = get_object_or_404(ProdutoFoto, pk=foto_pk, produto=produto)
    if acao == "apagar":
        foto.imagem.delete(save=False)
        foto.delete()
        messages.success(request, "Foto apagada.")
    elif acao == "principal":
        with transaction.atomic():
            fotos = list(produto.fotos.exclude(pk=foto.pk).order_by("ordem"))
            for ordem, outra in enumerate([foto, *fotos], start=1):
                if outra.ordem != ordem:
                    outra.ordem = ordem
                    outra.save(update_fields=["ordem", "atualizado_em"])
        messages.success(request, "Foto principal trocada.")
    else:
        raise PermissionDenied
    return redirect(f"{produto_url(produto)}#fotos")


# --- Reviews ------------------------------------------------------------------


@equipe("avaliacoes.view_avaliacao")
def avaliacoes(request):
    status = request.GET.get("status", Avaliacao.Status.PENDENTE)
    if status not in Avaliacao.Status.values:
        status = Avaliacao.Status.PENDENTE
    lista = (
        Avaliacao.objects.filter(status=status)
        .select_related("produto", "autor")
        .order_by("-criado_em")
    )
    contagem = dict(Avaliacao.objects.values_list("status").annotate(n=Count("pk")))
    return render(
        request,
        "gestao/avaliacoes.html",
        {
            "pagina": Paginator(lista, 20).get_page(request.GET.get("pagina")),
            "status": status,
            "opcoes": [(v, n, contagem.get(v, 0)) for v, n in Avaliacao.Status.choices],
            "secao": "avaliacoes",
        },
    )


@require_POST
@equipe("avaliacoes.change_avaliacao")
def moderar(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    form = RespostaForm(request.POST)
    form.is_valid()
    acao = request.POST.get("acao")
    novos = {"publicar": Avaliacao.Status.PUBLICADA, "ocultar": Avaliacao.Status.OCULTA}
    if acao in novos:
        avaliacao.status = novos[acao]
    avaliacao.resposta_loja = form.cleaned_data.get("resposta_loja", avaliacao.resposta_loja)
    avaliacao.save(update_fields=["status", "resposta_loja", "atualizado_em"])
    messages.success(
        request,
        {"publicar": "Avaliação publicada.", "ocultar": "Avaliação ocultada."}.get(
            acao, "Resposta salva."
        ),
    )
    voltar = request.POST.get("voltar_status", "")
    if voltar not in Avaliacao.Status.values:
        voltar = Avaliacao.Status.PENDENTE
    return redirect(f"{reverse('gestao:avaliacoes')}?status={voltar}")
