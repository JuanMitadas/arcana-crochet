"""Configurações do projeto Arcana Crochet.

Tudo que muda entre ambientes vem de variáveis de ambiente (ver .env.example).
"""

import os
from pathlib import Path

import environ
from django.utils.csp import CSP

from .ssm import carregar_parametros

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")
# Na AWS os segredos ficam no SSM Parameter Store (ver docs/deploy.md).
carregar_parametros(os.environ.get("AWS_SSM_PREFIX", ""))

# --- Núcleo -----------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8000")
# Em produção use um caminho difícil de adivinhar.
ADMIN_URL = env("ADMIN_URL", default="admin/")

# Na AWS, o CloudFront envia este segredo em todo pedido à Lambda; pedidos sem ele
# (alguém chamando a URL da Lambda direto, sem passar pelo CloudFront) recebem 403.
ORIGEM_SEGREDO = env("ORIGEM_SEGREDO", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    # terceiros
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "django_htmx",
    # projeto
    "apps.core",
    "apps.contas",
    "apps.catalogo",
    "apps.pedidos",
    "apps.avaliacoes",
]

MIDDLEWARE = [
    "apps.core.middleware.OrigemCloudFrontMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.contexto.loja",
                "apps.catalogo.contexto.menu_categorias",
                "apps.pedidos.contexto.sacola",
            ],
        },
    },
]

# --- Banco de dados ---------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if env.bool("DATABASE_POOLER", default=False):
    # Conexão "pooled" do Neon (PgBouncer em modo transação): sem prepared statements
    # nem cursores no servidor, que não sobrevivem à troca de conexão entre transações.
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autenticação -----------------------------------------------------------

AUTH_USER_MODEL = "contas.Usuario"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_REDIRECT_URL = "pedidos:lista"
LOGIN_URL = "account_login"

# django-allauth: login só por e-mail, com verificação obrigatória.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
# Autenticação rápida: código de 6 dígitos por e-mail para confirmar o cadastro
# e para entrar sem senha (útil no checkout).
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Arcana Crochet] "
ACCOUNT_RATE_LIMITS = {
    # 10 falhas por minuto por IP e 5 a cada 15 minutos por conta.
    "login_failed": "10/m/ip,5/900s/key",
}
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Arcana Crochet"

# Na AWS, uma CloudFront Function grava o IP do visitante em X-Arcana-Ip (e apaga
# qualquer valor enviado pelo próprio visitante). Sem isso, todos os pedidos teriam o
# mesmo IP e o limite de tentativas de login valeria para a loja inteira.
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = env("TRUSTED_CLIENT_IP_HEADER", default=None)

# --- Internacionalização ----------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Arquivos estáticos e uploads -------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

# Na AWS (MIDIA_BUCKET definido), as fotos vão para o S3 e são servidas pelo
# CloudFront no mesmo domínio do site, em /media/.
MIDIA_BUCKET = env("MIDIA_BUCKET", default="")
if MIDIA_BUCKET:
    media_storage = {
        "BACKEND": "apps.core.storage.MidiaS3",
        "OPTIONS": {
            "bucket_name": MIDIA_BUCKET,
            "location": "media",
            "region_name": env("AWS_REGION", default="sa-east-1"),
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
        },
    }
else:
    media_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": media_storage,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# A URL da Lambda aceita no máximo 6 MB por pedido: fotos maiores precisam ser
# reduzidas antes do envio (ou, no futuro, enviadas direto ao S3).
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- E-mail -----------------------------------------------------------------

# EMAIL_URL no formato do django-environ, ex.: smtp+tls://usuario:senha@smtp.resend.com:587
_email = env.email("EMAIL_URL", default="consolemail://")
_opcoes_smtp = {
    "host": _email.get("EMAIL_HOST"),
    "port": _email.get("EMAIL_PORT"),
    "username": _email.get("EMAIL_HOST_USER"),
    "password": _email.get("EMAIL_HOST_PASSWORD"),
    "use_tls": _email.get("EMAIL_USE_TLS"),
    "use_ssl": _email.get("EMAIL_USE_SSL"),
    "timeout": 10,
}
MAILERS = {
    "default": {
        "BACKEND": _email["EMAIL_BACKEND"],
        "OPTIONS": (
            {chave: valor for chave, valor in _opcoes_smtp.items() if valor not in (None, "")}
            if _email["EMAIL_BACKEND"].endswith("smtp.EmailBackend")
            else {}
        ),
    }
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Arcana Crochet <nao-responda@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Cache -------------------------------------------------------------------

# Na Lambda cada instância tem a própria memória, então o cache (usado no limite de
# tentativas de login) fica no banco: CACHE_URL=dbcache://cache_django.
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# --- Segurança --------------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:", *env.list("CSP_IMG_SRC", default=[])],
    "font-src": [CSP.SELF],
    # ViaCEP preenche o endereço a partir do CEP no checkout.
    "connect-src": [CSP.SELF, "https://viacep.com.br"],
    "media-src": [CSP.SELF, *env.list("CSP_IMG_SRC", default=[])],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}

if not DEBUG:
    # O HTTPS termina no CloudFront/URL da Lambda, que informam o protocolo original
    # neste cabeçalho.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    # Preload só depois de o domínio estar estável em HTTPS; é difícil de desfazer.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Atrás do CloudFront, o domínio que o visitante digitou chega em X-Forwarded-Host
# (gravado pela CloudFront Function; o Host original não é repassado à Lambda).
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=False)

# --- Regras comerciais da loja ---------------------------------------------

LOJA = {
    "PIX_DESCONTO_PCT": env.int("LOJA_PIX_DESCONTO_PCT", default=5),
    "PARCELAS_SEM_JUROS": env.int("LOJA_PARCELAS_SEM_JUROS", default=3),
    "PARCELA_MINIMA_CENTAVOS": env.int("LOJA_PARCELA_MINIMA_CENTAVOS", default=2000),
    "FRETE_GRATIS_A_PARTIR_CENTAVOS": env.int("LOJA_FRETE_GRATIS_A_PARTIR_CENTAVOS", default=29900),
    "CEP_ORIGEM": env("LOJA_CEP_ORIGEM", default="06700000"),
    "WHATSAPP": env("LOJA_WHATSAPP", default=""),
    "EMAIL_ATENDIMENTO": env("LOJA_EMAIL_ATENDIMENTO", default="contato@arcanacrochet.com.br"),
    "INSTAGRAM": env("LOJA_INSTAGRAM", default="arcanacrochet"),
}

# --- Logs -------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
