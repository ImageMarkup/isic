from datetime import datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

from django.utils.encoding import filepath_to_uri
from storages.backends.s3boto3 import S3Boto3Storage


def generate_upload_to(instance, filename) -> str:
    return str(uuid4())


class CacheableCloudFrontStorage(S3Boto3Storage):
    @staticmethod
    def next_expiration_time(now=None):
        # returns a time > 6 days but <= 7.
        now = now if now else datetime.utcnow()
        return now.replace(second=0, microsecond=0, minute=0, hour=0) + timedelta(days=7)

    # This is copied from upstream with minor modifications, subclassing in a cleaner way wasn't
    # possible.
    def url(self, name, parameters=None, expire=None, http_method=None):
        assert expire is None and http_method is None, 'Arguments not supported by custom storage.'

        # Preserve the trailing slash after normalizing the path.
        name = self._normalize_name(self._clean_name(name))
        params = parameters.copy() if parameters else {}

        if self.custom_domain:
            url = '{}//{}/{}{}'.format(
                self.url_protocol,
                self.custom_domain,
                filepath_to_uri(name),
                f'?{urlencode(params)}' if params else '',
            )

            if self.querystring_auth and self.cloudfront_signer:
                expiration = self.next_expiration_time()
                return self.cloudfront_signer.generate_presigned_url(url, date_less_than=expiration)

            return url
