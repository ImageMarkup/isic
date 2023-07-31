from datetime import datetime, timedelta
import io
from urllib.parse import urlencode
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
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
        assert expire is None and http_method is None, "Arguments not supported by custom storage."

        # Preserve the trailing slash after normalizing the path.
        name = self._normalize_name(self._clean_name(name))
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


try:
    from minio_storage.storage import MinioMediaStorage

    class MinioS3ProxyStorage(MinioMediaStorage):
        """
        A storage backend that proxies to S3 if the file doesn't exist in Minio.

        This is useful for local development enviroments that don't have a full copy of the
        production images. Note that requests to the development server will be slower than
        requests normal, since the file will be downloaded from S3 on the first request.

        Enabling this also requires disabling ISIC_PLACEHOLDER_IMAGES.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def url(self, name: str, *args, **kwargs) -> str:
            exists_in_minio = super().exists(name)

            if not exists_in_minio:
                upstream_file = io.BytesIO()
                s3 = boto3.resource("s3")
                bucket = s3.Bucket("isic-storage")
                upstream_obj = bucket.Object(name)

                try:
                    upstream_obj.download_fileobj(upstream_file)
                except ClientError as e:
                    if e.response["Error"]["Code"] != "404":
                        raise e
                else:
                    size = upstream_file.tell()
                    upstream_file.seek(0)
                    self.client.put_object(self.bucket_name, name, upstream_file, size)

            return super().url(name, *args, **kwargs)

except ImportError:
    pass
