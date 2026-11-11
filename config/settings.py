"""Arcana Crochet project settings.

Everything that changes between environments comes from environment variables
(see .env.example).
"""

import os
from pathlib import Path

import environ
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.csp import CSP

from .ssm import carregar_parametros

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")
# On AWS, secrets live in SSM Parameter Store (see docs/deploy.md).
carregar_parametros(os.environ.get("AWS_SSM_PREFIX", ""))

# --- Core -------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8000")
# In production use a path that is hard to guess.
ADMIN_URL = env("ADMIN_URL", default="admin/")

# On AWS, CloudFront sends this secret with every request to the Lambda; requests
# without it (someone calling the Lambda URL directly, bypassing CloudFront) get 403.
ORIGEM_SEGREDO = env("ORIGEM_SEGREDO", default="")

INSTALLED_APPS = [
    # Admin theme; must come before django.contrib.admin.
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # third party
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "django_htmx",
    # project
    "apps.core",
    "apps.contas",
    "apps.catalogo",
    "apps.pedidos",
    "apps.avaliacoes",
    "apps.gestao",
]

MIDDLEWARE = [
    "apps.core.middleware.OrigemCloudFrontMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "apps.core.middleware.CspPainelMiddleware",
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

# --- Database ---------------------------------------------------------------

DSQL_ENDPOINT = env("DSQL_ENDPOINT", default="")
if DSQL_ENDPOINT:
    # Aurora DSQL on AWS. There is no password: the connector signs a short-lived IAM
    # token for every new connection with the Lambda's (or your) AWS credentials.
    DATABASES = {
        "default": {
            "ENGINE": "config.dsql",
            "HOST": DSQL_ENDPOINT,
            "PORT": env.int("DSQL_PORT", default=5432),
            "NAME": env("DSQL_DBNAME", default="postgres"),
            "USER": env("DSQL_USER", default="admin"),
            "OPTIONS": {
                "sslmode": env("DSQL_SSLMODE", default="require"),
                **({"region": env("DSQL_REGION")} if env("DSQL_REGION", default="") else {}),
            },
            # Integer ids (Django, allauth, order items) as identity columns instead of
            # the adapter's default of turning every AutoField into a UUID. CACHE 1 keeps
            # them sequential: with DSQL's other option (65536) every new connection
            # skips ahead 65536 ids, and Django's integer foreign keys would overflow.
            "USE_SEQUENCE_AUTOFIELDS": True,
            "SEQUENCE_CACHE_SIZE": 1,
            # DSQL closes connections after one hour.
            "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=300),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    # Local development, CI and docker-compose: plain PostgreSQL.
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Aurora DSQL can't change a column's type, drop a column or a NOT NULL, and these
# apps did all of that over the years. config/migracoes/ holds their migrations
# rebuilt as a single 0001 with the final schema, plus empty files with the original
# names so dependencies still resolve. tests/test_dsql.py fails when an upgrade
# adds a migration that is missing here.
MIGRATION_MODULES = {
    app: f"config.migracoes.{app}" for app in ("contenttypes", "auth", "account", "mfa")
}

# --- Authentication ---------------------------------------------------------

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

# django-allauth: email-only login, with mandatory verification.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
# Quick authentication: a 6-digit code by email to confirm the sign-up and to log in
# without a password (handy at checkout).
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Arcana Crochet] "
ACCOUNT_RATE_LIMITS = {
    # 10 failures per minute per IP and 5 every 15 minutes per account.
    "login_failed": "10/m/ip,5/900s/key",
}
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Arcana Crochet"

# On AWS, a CloudFront Function writes the visitor's IP to X-Arcana-Ip (and drops
# any value the visitor sent). Without it every request would have the same IP and
# the login attempt limit would apply to the whole store.
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = env("TRUSTED_CLIENT_IP_HEADER", default=None)

# --- Internationalization ---------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Static files and uploads -----------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

# On AWS (MIDIA_BUCKET set), photos go to S3 and are served by CloudFront on the
# site's own domain, under /media/.
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

# The Lambda URL accepts at most 6 MB per request: larger photos must be resized
# before upload (or, in the future, uploaded straight to S3).
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- E-mail -----------------------------------------------------------------

# EMAIL_URL in django-environ format, e.g. smtp+tls://user:password@smtp.resend.com:587
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

# On Lambda each instance has its own memory, so the cache (used by the login attempt
# limit) lives in the database: CACHE_URL=dbcache://cache_django. The table is
# created by a migration (apps.core.models.EntradaCache).
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# --- Security ---------------------------------------------------------------

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
    # ViaCEP fills in the address from the CEP at checkout.
    "connect-src": [CSP.SELF, "https://viacep.com.br"],
    "media-src": [CSP.SELF, *env.list("CSP_IMG_SRC", default=[])],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}

if not DEBUG:
    # HTTPS ends at CloudFront/the Lambda URL, which report the original protocol in
    # this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    # Preload only once the domain is stable on HTTPS; it is hard to undo.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Behind CloudFront, the domain the visitor typed arrives in X-Forwarded-Host (set
# by the CloudFront Function; the original Host isn't forwarded to the Lambda).
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=False)

# --- Admin (django-unfold) ----------------------------------------------------
# The admin theme needs Alpine.js (which evaluates its own expressions) and inline
# styles. CspPainelMiddleware applies this looser policy to ADMIN_URL only; the store
# and the management panel (/gestao/) keep SECURE_CSP.
SECURE_CSP_ADMIN = {
    **SECURE_CSP,
    "script-src": [CSP.SELF, CSP.NONCE, CSP.UNSAFE_EVAL],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
}


def _paleta(matiz: float, croma: list[float], luz: list[float]) -> dict[str, str]:
    """Unfold color scale (50-950) in OKLCH from a hue and lightness/chroma steps."""
    tons = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"]
    return {t: f"oklch({lz}% {c} {matiz})" for t, lz, c in zip(tons, luz, croma, strict=True)}


UNFOLD = {
    "SITE_TITLE": "Arcana Crochet",
    "SITE_HEADER": "Arcana Crochet",
    "SITE_SUBHEADER": "Painel completo",
    "SITE_URL": "/",
    "SITE_ICON": lambda request: static("img/marca/favicon-64.png"),
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "type": "image/png",
            "href": lambda request: static("img/marca/favicon-64.png"),
        }
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SITE_DROPDOWN": [
        {
            "icon": "storefront",
            "title": "Gestão da loja",
            "link": reverse_lazy("gestao:inicio"),
        },
        {"icon": "open_in_new", "title": "Ver a loja", "link": "/"},
    ],
    "SIDEBAR": {"show_search": True, "show_all_applications": True},
    "COLORS": {
        # Brand blue (#17597c is the 700 step) and a cool, slightly teal gray.
        "primary": _paleta(
            237,
            [0.015, 0.03, 0.05, 0.07, 0.085, 0.09, 0.088, 0.086, 0.075, 0.062, 0.048],
            [97.5, 94.5, 89, 81, 69, 57, 49.5, 44.1, 38, 32, 24],
        ),
        "base": _paleta(
            200,
            [0.006, 0.008, 0.012, 0.016, 0.022, 0.026, 0.03, 0.032, 0.03, 0.028, 0.024],
            [98.4, 96.6, 92.6, 87, 70.5, 55, 44.5, 37.2, 27.8, 21, 13],
        ),
    },
}

# --- Store business rules ---------------------------------------------------

LOJA = {
    "PIX_DESCONTO_PCT": env.int("LOJA_PIX_DESCONTO_PCT", default=5),
    "PARCELAS_SEM_JUROS": env.int("LOJA_PARCELAS_SEM_JUROS", default=3),
    "PARCELA_MINIMA_CENTAVOS": env.int("LOJA_PARCELA_MINIMA_CENTAVOS", default=2000),
    "FRETE_GRATIS_A_PARTIR_CENTAVOS": env.int("LOJA_FRETE_GRATIS_A_PARTIR_CENTAVOS", default=29900),
    "CEP_ORIGEM": env("LOJA_CEP_ORIGEM", default="06700000"),
    "WHATSAPP": env("LOJA_WHATSAPP", default=""),
    "EMAIL_ATENDIMENTO": env("LOJA_EMAIL_ATENDIMENTO", default="contato@arcanacrochet.com.br"),
    "INSTAGRAM": env("LOJA_INSTAGRAM", default="arcanacrochet"),
    # Perks bar above the header (Pix discount, installments, free shipping). Off for now.
    "FAIXA_VANTAGENS": env.bool("LOJA_FAIXA_VANTAGENS", default=False),
    # Pix straight to the store's account (apps/pedidos/pix.py). The key, name and city
    # show up in the customer's bank app; on AWS they live in SSM, not in the repo.
    "PIX_CHAVE": env("LOJA_PIX_CHAVE", default=""),
    "PIX_RECEBEDOR": env("LOJA_PIX_RECEBEDOR", default=""),
    "PIX_CIDADE": env("LOJA_PIX_CIDADE", default=""),
    # Unpaid orders are cancelled after this many hours and their pieces go back on sale.
    "PRAZO_PAGAMENTO_HORAS": env.int("LOJA_PRAZO_PAGAMENTO_HORAS", default=24),
}

# --- Logs -------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
