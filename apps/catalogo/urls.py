from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.home, name="home"),
    path("loja/", views.listagem, name="vitrine"),
    path("busca/", views.listagem, name="busca"),
    path("c/<slug:slug>/", views.listagem, name="categoria"),
    path("p/<slug:slug>/", views.produto_detalhe, name="produto"),
    path("p/<slug:slug>/frete/", views.produto_frete, name="produto_frete"),
]
