import io

import boto3
from botocore.exceptions import ClientError
from minio_storage.files import ReadOnlySpooledTemporaryFile
from minio_storage.storage import MinioMediaStorage


class StringableReadOnlySpooledTemporaryFile(ReadOnlySpooledTemporaryFile):
    def read(self, *args, **kwargs):
        if "r" not in self._mode:
            raise AttributeError("File was not opened in read mode.")
        if "b" in self._mode:
            return super().read(*args, **kwargs)

        return super().read(*args, **kwargs).decode()

    def readline(self, *args, **kwargs):
        if "r" not in self._mode:
            raise AttributeError("File was not opened in read mode.")
        if "b" in self._mode:
            return super().readline(*args, **kwargs)

        return super().readline(*args, **kwargs).decode()


class StringableMinioMediaStorage(MinioMediaStorage):
    file_class = StringableReadOnlySpooledTemporaryFile


class MinioS3ProxyStorage(StringableMinioMediaStorage):
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
                    raise
            else:
                size = upstream_file.tell()
                upstream_file.seek(0)
                self.client.put_object(self.bucket_name, name, upstream_file, size)

        return super().url(name, *args, **kwargs)
