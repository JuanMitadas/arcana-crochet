from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("sobre/", TemplateView.as_view(template_name="core/sobre.html"), name="sobre"),
    path(
        "trocas-e-devolucoes/",
        TemplateView.as_view(template_name="core/trocas.html"),
        name="trocas",
    ),
]
