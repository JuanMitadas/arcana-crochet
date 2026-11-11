from django.urls import path

from . import views

app_name = "gestao"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("pedidos/", views.pedidos, name="pedidos"),
    path("pedidos/<str:codigo>/", views.pedido, name="pedido"),
    path("pedidos/<str:codigo>/<slug:acao>/", views.acao_pedido, name="acao_pedido"),
    path("pecas/", views.pecas, name="pecas"),
    path("pecas/nova/", views.peca_form, name="peca_nova"),
    path("pecas/<uuid:pk>/", views.peca_form, name="peca"),
    path("pecas/<uuid:pk>/estoque/", views.estoque, name="estoque"),
    path("pecas/<uuid:pk>/fotos/", views.fotos, name="fotos"),
    path("pecas/<uuid:pk>/fotos/<uuid:foto_pk>/<slug:acao>/", views.foto_acao, name="foto_acao"),
    path("avaliacoes/", views.avaliacoes, name="avaliacoes"),
    path("avaliacoes/<uuid:pk>/", views.moderar, name="moderar"),
]
