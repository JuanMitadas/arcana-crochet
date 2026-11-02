from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.VitrineView.as_view(), name="vitrine"),
    path("p/<slug:slug>/", views.produto_detalhe, name="produto"),
]
