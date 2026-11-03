from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("sacola/", views.sacola, name="sacola"),
    path("sacola/adicionar/", views.adicionar, name="adicionar"),
    path("sacola/item/<uuid:variacao_id>/", views.atualizar_item, name="atualizar_item"),
    path("sacola/cupom/", views.aplicar_cupom, name="cupom"),
    path("sacola/frete/", views.calcular_frete, name="frete"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/identificacao/", views.checkout_identificacao, name="checkout_identificacao"),
    path("checkout/entrega/", views.checkout_entrega, name="checkout_entrega"),
    path("checkout/pagamento/", views.checkout_pagamento, name="checkout_pagamento"),
    path("checkout/revisao/", views.checkout_revisao, name="checkout_revisao"),
    path("minha-conta/", views.pedidos_lista, name="lista"),
    path("minha-conta/pedidos/<str:codigo>/", views.pedido_detalhe, name="detalhe"),
    path(
        "minha-conta/pedidos/<str:codigo>/simular-pagamento/",
        views.simular_pagamento,
        name="simular_pagamento",
    ),
    path("minha-conta/enderecos/", views.enderecos, name="enderecos"),
    path("minha-conta/avaliar/<int:item_id>/", views.avaliar, name="avaliar"),
]
