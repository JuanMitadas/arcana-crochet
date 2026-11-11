"""Forms of the management panel. Labels and messages are in Portuguese: the team reads them."""

import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.catalogo.models import (
    Categoria,
    Produto,
    ProdutoEspecificacao,
    ProdutoFoto,
    ProdutoVariacao,
)
from apps.pedidos.models import Pedido

FOTO_MAX_MB = 5


def formatar_reais(centavos: int | None) -> str:
    if centavos is None:
        return ""
    return f"{centavos / 100:.2f}".replace(".", ",")


class CampoReais(forms.CharField):
    """Money typed the Brazilian way ("129,90", "1.299,90", "129") stored in cents."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # maxlength only on the input: the cleaned value is an int, not text.
        self.widget.attrs.update({"inputmode": "decimal", "placeholder": "0,00", "maxlength": 14})

    def prepare_value(self, value):
        return formatar_reais(value) if isinstance(value, int) else value

    def to_python(self, value):
        texto = (super().to_python(value) or "").replace("R$", "").strip()
        if not texto:
            return None
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        if not re.fullmatch(r"\d+(\.\d{1,2})?", texto):
            raise ValidationError("Use só números, com vírgula para os centavos. Ex.: 129,90")
        try:
            return int((Decimal(texto) * 100).to_integral_value())
        except InvalidOperation as erro:
            raise ValidationError("Valor inválido.") from erro


class ProdutoForm(forms.ModelForm):
    preco_centavos = CampoReais(label="Preço (R$)")
    preco_promocional_centavos = CampoReais(
        label="Preço promocional (R$)",
        required=False,
        help_text="Deixe vazio se a peça não estiver em promoção.",
    )
    custo_centavos = CampoReais(
        label="Custo (R$)", required=False, help_text="Fio + horas de trabalho. Só a equipe vê."
    )

    class Meta:
        model = Produto
        fields = [
            "nome", "categoria", "status", "descricao", "preco_centavos",
            "preco_promocional_centavos", "custo_centavos", "disponibilidade",
            "prazo_producao_dias", "material", "cuidados", "peso_g", "altura_cm",
            "largura_cm", "comprimento_cm", "personalizavel", "destaque",
        ]  # fmt: skip
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 5}),
            "cuidados": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.select_related("pai").order_by(
            "pai__nome", "ordem", "nome"
        )
        self.fields["categoria"].label_from_instance = lambda c: (
            f"{c.pai.nome} › {c.nome}" if c.pai_id else c.nome
        )

    def clean_custo_centavos(self):
        return self.cleaned_data["custo_centavos"] or 0

    def clean(self):
        dados = super().clean()
        preco, promo = dados.get("preco_centavos"), dados.get("preco_promocional_centavos")
        if preco is not None and promo is not None and not 0 < promo < preco:
            self.add_error("preco_promocional_centavos", "O preço promocional precisa ser menor.")
        if dados.get("disponibilidade") == Produto.Disponibilidade.SOB_ENCOMENDA and not dados.get(
            "prazo_producao_dias"
        ):
            self.add_error("prazo_producao_dias", "Informe em quantos dias a peça fica pronta.")
        return dados

    def save(self, commit=True):
        produto = super().save(commit=False)
        if not produto.slug:
            produto.slug = slug_unico(produto.nome)
        if produto.status == Produto.Status.ATIVO and not produto.publicado_em:
            from django.utils import timezone

            produto.publicado_em = timezone.now()
        if commit:
            produto.save()
        return produto


def slug_unico(nome: str) -> str:
    base = slugify(nome)[:80] or "peca"
    slug, n = base, 2
    while Produto.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


class VariacaoForm(forms.ModelForm):
    preco_ajuste_centavos = CampoReais(
        label="Ajuste no preço (R$)", required=False, help_text="Ex.: 10,00 a mais no tamanho G."
    )
    estoque_inicial = forms.IntegerField(
        label="Estoque inicial", required=False, min_value=0, initial=0
    )

    class Meta:
        model = ProdutoVariacao
        fields = ["cor", "cor_hex", "tamanho", "preco_ajuste_centavos", "ativa", "sku"]
        widgets = {"cor_hex": forms.TextInput(attrs={"placeholder": "#17597c"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].required = False
        self.fields["sku"].help_text = "Deixe vazio para gerar sozinho."
        if not self.instance._state.adding:
            # Stock of existing variations changes through movements, not here.
            del self.fields["estoque_inicial"]

    def clean_preco_ajuste_centavos(self):
        return self.cleaned_data["preco_ajuste_centavos"] or 0


class BaseVariacaoFormSet(forms.BaseInlineFormSet):
    def save_new(self, form, commit=True):
        variacao = super().save_new(form, commit=False)
        if not variacao.sku:
            variacao.sku = sku_unico(self.instance, variacao)
        if commit:
            variacao.save()
        return variacao

    def clean(self):
        super().clean()
        ativas = [
            f for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("ativa")
        ]  # fmt: skip
        if not ativas:
            raise ValidationError("A peça precisa de pelo menos uma variação ativa.")


def sku_unico(produto: Produto, variacao: ProdutoVariacao) -> str:
    partes = [produto.slug, variacao.cor, variacao.tamanho]
    base = slugify("-".join(filter(None, partes))).upper()[:36] or "SKU"
    sku, n = base, 2
    while ProdutoVariacao.objects.filter(sku=sku).exists():
        sku, n = f"{base}-{n}", n + 1
    return sku


VariacaoFormSet = forms.inlineformset_factory(
    Produto,
    ProdutoVariacao,
    form=VariacaoForm,
    formset=BaseVariacaoFormSet,
    extra=1,
    can_delete=False,
)

EspecificacaoFormSet = forms.inlineformset_factory(
    Produto,
    ProdutoEspecificacao,
    fields=["nome", "valor"],
    extra=2,
    can_delete=True,
    labels={"nome": "Item", "valor": "Valor"},
    widgets={
        "nome": forms.TextInput(attrs={"placeholder": "Ex.: Altura"}),
        "valor": forms.TextInput(attrs={"placeholder": "Ex.: 18 cm"}),
    },
)


class EstoqueForm(forms.Form):
    variacao = forms.UUIDField(widget=forms.HiddenInput)
    quantidade = forms.IntegerField(
        label="Quantidade", help_text="Positiva para entrada, negativa para saída."
    )
    motivo = forms.CharField(label="Motivo", max_length=200, required=False)

    def clean_quantidade(self):
        quantidade = self.cleaned_data["quantidade"]
        if quantidade == 0:
            raise ValidationError("Informe uma quantidade diferente de zero.")
        return quantidade


class VariosArquivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoFotos(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariosArquivos(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, list | tuple) else [data]
        limpos = [super(CampoFotos, self).clean(arquivo, initial) for arquivo in arquivos]
        for arquivo in limpos:
            if arquivo.size > FOTO_MAX_MB * 1024 * 1024:
                raise ValidationError(f"Cada foto pode ter até {FOTO_MAX_MB} MB.")
        return limpos


class FotosForm(forms.Form):
    fotos = CampoFotos(label="Fotos")
    variacao = forms.ModelChoiceField(
        label="Variação",
        queryset=ProdutoVariacao.objects.none(),
        required=False,
        empty_label="Todas as variações",
    )
    texto_alternativo = forms.CharField(
        label="Descrição da foto",
        max_length=150,
        required=False,
        help_text="Para quem usa leitor de tela. Ex.: Urso azul de crochê sentado.",
    )

    def __init__(self, *args, produto: Produto, **kwargs):
        super().__init__(*args, **kwargs)
        self.produto = produto
        self.fields["variacao"].queryset = produto.variacoes.all()

    def salvar(self) -> int:
        ultima = self.produto.fotos.order_by("-ordem").values_list("ordem", flat=True).first()
        ordem = (ultima or 0) + 1
        texto = self.cleaned_data["texto_alternativo"] or self.produto.nome
        for i, arquivo in enumerate(self.cleaned_data["fotos"]):
            ProdutoFoto.objects.create(
                produto=self.produto,
                variacao=self.cleaned_data["variacao"],
                imagem=arquivo,
                texto_alternativo=texto,
                ordem=ordem + i,
            )
        return len(self.cleaned_data["fotos"])


class EnvioForm(forms.Form):
    codigo_rastreio = forms.CharField(label="Código de rastreio", max_length=40)
    transportadora = forms.CharField(
        label="Transportadora", max_length=60, required=False, initial="Correios"
    )


class CancelarForm(forms.Form):
    motivo = forms.CharField(label="Motivo", max_length=200, required=False)


class RespostaForm(forms.Form):
    resposta_loja = forms.CharField(
        label="Resposta da loja (aparece embaixo da avaliação)",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


ETAPAS_PEDIDO = {
    "pagar": ("Pix para confirmar", [Pedido.Status.AGUARDANDO_PAGAMENTO]),
    "separar": ("Para separar", [Pedido.Status.PAGO]),
    "enviar": ("Para enviar", [Pedido.Status.EM_SEPARACAO]),
    "caminho": ("A caminho", [Pedido.Status.ENVIADO]),
    "concluidos": ("Entregues", [Pedido.Status.ENTREGUE]),
    "cancelados": ("Cancelados", [Pedido.Status.CANCELADO]),
}
