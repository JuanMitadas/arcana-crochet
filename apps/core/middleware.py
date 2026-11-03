import hmac

from django.conf import settings
from django.http import HttpResponseForbidden

# O ping de aquecimento e o readiness check do Lambda Web Adapter chamam este
# caminho direto, sem passar pelo CloudFront.
CAMINHOS_LIVRES = ("/healthz/",)


class OrigemCloudFrontMiddleware:
    """Recusa pedidos que não vieram pelo CloudFront.

    A URL da Lambda é pública. Sem esta checagem, alguém poderia chamá-la direto e
    contornar o CloudFront (cache, HTTPS do domínio, cabeçalho com o IP real). O
    CloudFront envia o cabeçalho X-Arcana-Origem com um segredo que só ele conhece.
    Desligado quando ORIGEM_SEGREDO está vazio (desenvolvimento e testes).
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
