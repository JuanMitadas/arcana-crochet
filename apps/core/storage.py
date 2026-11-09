from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage
from storages.utils import clean_name


class MidiaS3(S3Storage):
    """Photos on S3, served by CloudFront on the same domain as the site.

    Files live in the bucket under "media/<path>" (the location option) and the URL
    returned is relative, "/media/<path>": CloudFront sends /media/* to S3. That way
    the same settings work on the custom domain and on the *.cloudfront.net address.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        return settings.MEDIA_URL + filepath_to_uri(clean_name(name)).lstrip("/")
