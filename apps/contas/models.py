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
    """Cliente da loja ou integrante da equipe. O login é sempre pelo e-mail."""

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
