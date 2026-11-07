"""Cancel orders not paid within LOJA_PRAZO_PAGAMENTO_HORAS (on AWS this runs hourly)."""

from django.core.management.base import BaseCommand

from apps.pedidos.servicos import cancelar_vencidos


class Command(BaseCommand):
    help = "Cancel unpaid orders past the payment deadline and release their pieces."

    def handle(self, *args, **options):
        self.stdout.write(f"Cancelled orders: {cancelar_vencidos()}")
