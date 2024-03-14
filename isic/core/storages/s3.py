from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from botocore.config import Config
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage
from storages.utils import clean_name


class CacheableCloudFrontStorage(S3Storage):
    def __init__(self, **settings):
        super().__init__(**settings)

        self.config = self.config.merge(
            Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 5})
        )

    @staticmethod
    def next_expiration_time(now=None):
        # returns a time > 6 days but <= 7.
        now = now if now else datetime.now(tz=UTC)
        return now.replace(second=0, microsecond=0, minute=0, hour=0) + timedelta(days=7)

    # This is copied from upstream with minor modifications, subclassing in a cleaner way wasn't
    # possible.
    def url(self, name, parameters=None, expire=None, http_method=None):
        if expire is not None or http_method is not None:
            raise ValueError("expire and http_method are not supported by this storage backend.")

        # Preserve the trailing slash after normalizing the path.
        name = self._normalize_name(clean_name(name))
        params = parameters.copy() if parameters else {}

        if self.custom_domain:
            url = "{}//{}/{}{}".format(
                self.url_protocol,
                self.custom_domain,
                filepath_to_uri(name),
                f"?{urlencode(params)}" if params else "",
            )

            if self.querystring_auth and self.cloudfront_signer:
                expiration = self.next_expiration_time()
                return self.cloudfront_signer.generate_presigned_url(url, date_less_than=expiration)

            return url
