from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def healthz(request):
    """Responde se a aplicação está no ar.

    Aceita POST porque o Lambda Web Adapter entrega aqui os eventos que não são
    HTTP, como o ping de aquecimento do EventBridge (AWS_LWA_PASS_THROUGH_PATH).

    Por padrão não consulta o banco: o ping de aquecimento roda a cada 5 minutos e,
    se acordasse o Neon, gastaria a cota grátis de processamento. Use ?banco=1 no
    monitor de disponibilidade para checar também o banco.
    """
    if request.GET.get("banco") == "1":
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return JsonResponse({"status": "erro", "banco": "indisponivel"}, status=503)
    return JsonResponse({"status": "ok"})
