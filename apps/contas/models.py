from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.ids import uuid7


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _criar(self, email, password, **campos):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        usuario = self.model(email=self.normalize_email(email).lower(), **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **campos):
        campos.setdefault("papel", Usuario.Papel.CLIENTE)
        campos.setdefault("is_superuser", False)
        return self._criar(email, password, **campos)

    def create_superuser(self, email, password=None, **campos):
        campos["papel"] = Usuario.Papel.ADMIN
        campos["is_superuser"] = True
        return self._criar(email, password, **campos)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Store customer or team member. Login is always by email."""

    class Papel(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        ATENDENTE = "atendente", "Atendente"
        ADMIN = "admin", "Administrador"

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField("e-mail", unique=True)
    nome_completo = models.CharField("nome completo", max_length=150, blank=True)
    nome_exibicao = models.CharField(
        "nome de exibição",
        max_length=60,
        blank=True,
        help_text="Aparece nas avaliações públicas.",
    )
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.CLIENTE)
    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField(
        "acesso ao painel",
        default=False,
        editable=False,
        help_text="Calculado a partir do papel.",
    )
    date_joined = models.DateTimeField("cadastrado em", default=timezone.now)
    termos_versao = models.CharField("versão dos termos aceitos", max_length=20, blank=True)
    termos_aceitos_em = models.DateTimeField("termos aceitos em", null=True, blank=True)
    observacao_interna = models.TextField(
        "observação interna",
        blank=True,
        help_text="Visível só para a equipe. Registre fatos, não opiniões.",
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        self.is_staff = self.papel in (self.Papel.ATENDENTE, self.Papel.ADMIN)
        super().save(*args, **kwargs)

    @property
    def eh_equipe(self) -> bool:
        return self.is_staff


class Endereco(models.Model):
    """Shipping address saved by the customer."""

    UFS = [
        (uf, uf)
        for uf in (
            "AC",
            "AL",
            "AM",
            "AP",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MG",
            "MS",
            "MT",
            "PA",
            "PB",
            "PE",
            "PI",
            "PR",
            "RJ",
            "RN",
            "RO",
            "RR",
            "RS",
            "SC",
            "SE",
            "SP",
            "TO",
        )  # fmt: skip
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="enderecos")
    apelido = models.CharField(max_length=30, blank=True, help_text="Ex.: Casa, Trabalho.")
    destinatario = models.CharField("destinatário", max_length=120)
    telefone = models.CharField(max_length=20)
    cep = models.CharField("CEP", max_length=8)
    logradouro = models.CharField("rua", max_length=150)
    numero = models.CharField("número", max_length=20)
    complemento = models.CharField(max_length=80, blank=True)
    bairro = models.CharField(max_length=80)
    cidade = models.CharField(max_length=80)
    uf = models.CharField("UF", max_length=2, choices=UFS)
    padrao = models.BooleanField("endereço principal", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "endereço"
        verbose_name_plural = "endereços"
        ordering = ["-padrao", "-criado_em"]

    def __str__(self):
        return f"{self.logradouro}, {self.numero} · {self.cidade}/{self.uf}"

    @property
    def cep_formatado(self) -> str:
        return f"{self.cep[:5]}-{self.cep[5:]}" if len(self.cep) == 8 else self.cep

    def como_dict(self) -> dict:
        """Frozen copy for the order: changing the address later doesn't touch old orders."""
        campos = [
            "destinatario", "telefone", "cep", "logradouro", "numero",
            "complemento", "bairro", "cidade", "uf",
        ]  # fmt: skip
        return {campo: getattr(self, campo) for campo in campos}
