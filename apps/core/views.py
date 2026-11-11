import json

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def healthz(request):
    """Report whether the application is up.

    Accepts POST because the Lambda Web Adapter delivers non-HTTP events here, such
    as the EventBridge warm-up ping (AWS_LWA_PASS_THROUGH_PATH).

    A plain GET doesn't touch the database (the adapter's readiness check uses it);
    ?banco=1 in the uptime monitor checks the database too. The warm-up ping
    (``{"aquecimento": true}``, every 5 minutes) runs ``SELECT 1`` so the instance
    keeps its database connection open: otherwise the first visitor after a quiet
    spell pays for a new TLS connection and IAM token. It costs a tiny amount of
    Aurora DSQL usage, well within the free tier.

    The hourly EventBridge event ``{"tarefa": "cancelar_pedidos_vencidos"}`` cancels
    unpaid orders past the deadline. Anyone reaching this URL could send it too, which
    is harmless: it only cancels orders that are already overdue.
    """
    if request.method == "POST" and _tarefa(request) == "cancelar_pedidos_vencidos":
        from apps.pedidos.servicos import cancelar_vencidos

        return JsonResponse({"status": "ok", "cancelados": cancelar_vencidos()})
    if request.GET.get("banco") == "1" or (request.method == "POST" and _aquecimento(request)):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return JsonResponse({"status": "erro", "banco": "indisponivel"}, status=503)
    return JsonResponse({"status": "ok"})


def _tarefa(request) -> str:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        return ""
    return corpo.get("tarefa", "") if isinstance(corpo, dict) else ""


def _aquecimento(request) -> bool:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        return False
    return isinstance(corpo, dict) and corpo.get("aquecimento") is True
