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

    By default it doesn't query the database: the warm-up ping runs every 5 minutes
    and would spend Aurora DSQL usage for nothing. Use ?banco=1 in the uptime
    monitor to check the database too.
    """
    if request.GET.get("banco") == "1":
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return JsonResponse({"status": "erro", "banco": "indisponivel"}, status=503)
    return JsonResponse({"status": "ok"})
