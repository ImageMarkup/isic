from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3StaticStorage, S3Storage
from storages.utils import clean_name

from isic.core.storages import PreventRenamingMixin


class CacheableCloudFrontStorage(PreventRenamingMixin, S3Storage):
    @staticmethod
    def next_expiration_time(now=None):
        # returns a time > 6 days but <= 7.
        now = now if now else datetime.now(tz=UTC)
        return now.replace(second=0, microsecond=0, minute=0, hour=0) + timedelta(days=7)

    # This is copied from upstream with minor modifications, subclassing in a cleaner way wasn't
    # possible.
    def url(self, name, parameters=None, expire=None, http_method=None):
        # If expire or http_method is set, defer to the parent implementation. At the moment this is
        # only done with generate_staff_image_list_metadata_csv.
        if expire is not None or http_method is not None:
            return super().url(name, parameters=parameters, expire=expire, http_method=http_method)

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


class S3StaticStorage(PreventRenamingMixin, S3StaticStorage):
    pass
