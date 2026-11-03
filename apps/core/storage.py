from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage
from storages.utils import clean_name


class MidiaS3(S3Storage):
    """Fotos no S3, servidas pelo CloudFront no mesmo domínio do site.

    O arquivo fica no bucket em "media/<caminho>" (opção location) e a URL devolvida
    é relativa, "/media/<caminho>": o CloudFront manda /media/* para o S3. Assim a
    mesma configuração funciona no domínio próprio e no endereço *.cloudfront.net.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        return settings.MEDIA_URL + filepath_to_uri(clean_name(name)).lstrip("/")
