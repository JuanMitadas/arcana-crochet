from django import forms

from apps.avaliacoes.models import Avaliacao
from apps.contas.models import Endereco

from .frete import limpar_cep


class EnderecoForm(forms.ModelForm):
    # Aceita o CEP com hífen (9 caracteres); clean_cep guarda só os 8 números.
    cep = forms.CharField(
        label="CEP",
        max_length=9,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "postal-code",
                "placeholder": "00000-000",
                "data-cep": "",
                "maxlength": "9",
            }
        ),
    )

    class Meta:
        model = Endereco
        fields = [
            "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
            "destinatario", "telefone", "apelido", "padrao",
        ]  # fmt: skip
        widgets = {
            "logradouro": forms.TextInput(attrs={"autocomplete": "address-line1"}),
            "numero": forms.TextInput(attrs={"inputmode": "numeric"}),
            "complemento": forms.TextInput(
                attrs={"autocomplete": "address-line2", "placeholder": "Apto, bloco, casa"}
            ),
            "bairro": forms.TextInput(attrs={"autocomplete": "address-level3"}),
            "cidade": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "uf": forms.Select(attrs={"autocomplete": "address-level1"}),
            "destinatario": forms.TextInput(attrs={"autocomplete": "name"}),
            "telefone": forms.TextInput(
                attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "(11) 90000-0000"}
            ),
            "apelido": forms.TextInput(attrs={"placeholder": "Casa, trabalho…"}),
        }
        labels = {"destinatario": "Quem vai receber", "padrao": "Usar como endereço principal"}

    def clean_cep(self):
        cep = limpar_cep(self.cleaned_data["cep"])
        if len(cep) != 8:
            raise forms.ValidationError("Digite um CEP com 8 números.")
        return cep

    def clean_telefone(self):
        numeros = "".join(c for c in self.cleaned_data["telefone"] if c.isdigit())
        if len(numeros) not in (10, 11):
            raise forms.ValidationError("Digite o telefone com DDD.")
        return numeros


class AvaliacaoForm(forms.ModelForm):
    nota = forms.TypedChoiceField(
        choices=[(n, f"{n} de 5") for n in range(5, 0, -1)],
        coerce=int,
        widget=forms.RadioSelect,
        label="Sua nota",
    )

    class Meta:
        model = Avaliacao
        fields = ["nota", "titulo", "comentario"]
        labels = {"titulo": "Título (opcional)", "comentario": "Conte como foi"}
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Ficou ainda mais lindo ao vivo"}),
            "comentario": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Acabamento, tamanho, cor, embalagem, prazo de entrega…",
                }
            ),
        }
