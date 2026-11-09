from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Arcana Crochet: painel"
admin.site.site_title = "Arcana Crochet"
admin.site.index_title = "Administração da loja"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("conta/", include("allauth.urls")),
    path("", include("apps.catalogo.urls")),
    path("", include("apps.pedidos.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
