from datetime import timedelta
import io

import boto3
from botocore.exceptions import ClientError
from minio_storage import MinioMediaStorage

from isic.core.storages import PreventRenamingMixin


class PreventRenamingMinioMediaStorage(PreventRenamingMixin, MinioMediaStorage):
    pass


class PlaceholderMinioStorage(PreventRenamingMinioMediaStorage):
    def url(self, name: str | None, *, max_age: timedelta | None = None) -> str:
        if name is None:
            raise ValueError("name must be provided.")

        # Exclude PNG images, since those should be 16-bit)
        if name.endswith(".jpg"):
            size = 256 if "thumbnail" in name else 1000
            return f"https://picsum.photos/seed/{hash(name)}/{size}"

        return super().url(name, max_age=max_age)


class S3ProxyMinioStorage(PreventRenamingMinioMediaStorage):
    """
    A storage backend which proxies to S3 if the file doesn't exist in Minio.

    This is useful for local development environments that don't have a full copy of the
    production images. Note that requests to the development server will be slower than
    requests normal, since the file will be downloaded from S3 on the first request.
    """

    def __init__(self, *args, **kwargs):
        self.upstream_bucket_name = kwargs.pop("upstream_bucket_name")
        super().__init__(*args, **kwargs)

    def _ensure_exists(self, name: str) -> None:
        exists_in_minio = super().exists(name)

        if not exists_in_minio:
            upstream_file = io.BytesIO()
            s3 = boto3.resource("s3")
            bucket = s3.Bucket(self.upstream_bucket_name)
            upstream_obj = bucket.Object(name)

            try:
                upstream_obj.download_fileobj(upstream_file)
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise
            else:
                size = upstream_file.tell()
                upstream_file.seek(0)
                self.client.put_object(self.bucket_name, name, upstream_file, size)

    def open(self, name, *args, **kwargs):
        self._ensure_exists(name)
        return super().open(name, *args, **kwargs)

    def url(self, name: str | None, *, max_age: timedelta | None = None) -> str:
        if name is None:
            raise ValueError("name must be provided.")
        self._ensure_exists(name)
        return super().url(name, max_age=max_age)
