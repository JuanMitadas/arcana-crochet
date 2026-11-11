import hmac

from django.conf import settings
from django.http import HttpResponseForbidden

# The warm-up ping and the Lambda Web Adapter readiness check call this path
# directly, without going through CloudFront.
CAMINHOS_LIVRES = ("/healthz/",)


class OrigemCloudFrontMiddleware:
    """Reject requests that didn't come through CloudFront.

    The Lambda URL is public. Without this check, someone could call it directly and
    bypass CloudFront (cache, the domain's HTTPS, the real-IP header). CloudFront
    sends the X-Arcana-Origem header with a secret only it knows. Disabled when
    ORIGEM_SEGREDO is empty (development and tests).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.segredo = settings.ORIGEM_SEGREDO.encode()

    def __call__(self, request):
        if self.segredo and request.path not in CAMINHOS_LIVRES:
            recebido = request.headers.get("X-Arcana-Origem", "").encode()
            if not hmac.compare_digest(recebido, self.segredo):
                return HttpResponseForbidden("Acesso direto não permitido.")
        return self.get_response(request)


class CspPainelMiddleware:
    """Looser Content-Security-Policy for the admin only (settings.SECURE_CSP_ADMIN).

    Listed right after Django's CSP middleware, so it sees the response first and
    leaves the policy choice on it, the same way the ``csp_override`` decorator does.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixo = "/" + settings.ADMIN_URL.lstrip("/")

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.prefixo):
            response._csp_config = settings.SECURE_CSP_ADMIN
        return response
