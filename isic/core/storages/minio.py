import functools
import io

import boto3
from botocore.exceptions import ClientError
from django.core.files import File
import minio
from minio_storage.files import ReadOnlySpooledTemporaryFile
from minio_storage.policy import Policy
from minio_storage.storage import MinioStorage, create_minio_client_from_settings, get_setting


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


class FixedMinioMediaStorage(MinioStorage):
    # From https://github.com/py-pa/django-minio-storage/pull/139
    file_class = StringableReadOnlySpooledTemporaryFile

    # From https://github.com/py-pa/django-minio-storage/pull/144
    def __init__(  # noqa: C901, PLR0913
        self,
        *,
        minio_client: minio.Minio | None = None,
        bucket_name: str | None = None,
        base_url: str | None = None,
        file_class: type[File] | None = None,
        auto_create_bucket: bool | None = None,
        presign_urls: bool | None = None,
        auto_create_policy: bool | None = None,
        policy_type: Policy | None = None,
        object_metadata: dict[str, str] | None = None,
        backup_format: str | None = None,
        backup_bucket: str | None = None,
        assume_bucket_exists: bool | None = None,
    ):
        if minio_client is None:
            minio_client = create_minio_client_from_settings()
        if bucket_name is None:
            bucket_name = get_setting("MINIO_STORAGE_MEDIA_BUCKET_NAME")
        if base_url is None:
            base_url = get_setting("MINIO_STORAGE_MEDIA_URL", None)
        if auto_create_bucket is None:
            auto_create_bucket = get_setting("MINIO_STORAGE_AUTO_CREATE_MEDIA_BUCKET", False)  # noqa: FBT003
        if presign_urls is None:
            presign_urls = get_setting("MINIO_STORAGE_MEDIA_USE_PRESIGNED", False)  # noqa: FBT003
        auto_create_policy_setting = get_setting(
            "MINIO_STORAGE_AUTO_CREATE_MEDIA_POLICY", "GET_ONLY"
        )
        if auto_create_policy is None:
            auto_create_policy = (
                True if isinstance(auto_create_policy_setting, str) else auto_create_policy_setting
            )
        if policy_type is None:
            policy_type = (
                Policy(auto_create_policy_setting)
                if isinstance(auto_create_policy_setting, str)
                else Policy.get
            )
        if object_metadata is None:
            object_metadata = get_setting("MINIO_STORAGE_MEDIA_OBJECT_METADATA", None)
        if backup_format is None:
            backup_format = get_setting("MINIO_STORAGE_MEDIA_BACKUP_FORMAT", None)
        if backup_bucket is None:
            backup_bucket = get_setting("MINIO_STORAGE_MEDIA_BACKUP_BUCKET", None)
        if assume_bucket_exists is None:
            assume_bucket_exists = get_setting("MINIO_STORAGE_ASSUME_MEDIA_BUCKET_EXISTS", False)  # noqa: FBT003
        super().__init__(
            minio_client,
            bucket_name,
            base_url=base_url,
            file_class=file_class,
            auto_create_bucket=auto_create_bucket,
            presign_urls=presign_urls,
            auto_create_policy=auto_create_policy,
            policy_type=policy_type,
            object_metadata=object_metadata,
            backup_format=backup_format,
            backup_bucket=backup_bucket,
            assume_bucket_exists=assume_bucket_exists,
        )


StaticFixedMinioMediaStorage = functools.partial(
    FixedMinioMediaStorage,
    presign_urls=False,
)


class MinioS3ProxyStorage(FixedMinioMediaStorage):
    """
    A storage backend that proxies to S3 if the file doesn't exist in Minio.

    This is useful for local development enviroments that don't have a full copy of the
    production images. Note that requests to the development server will be slower than
    requests normal, since the file will be downloaded from S3 on the first request.

    Enabling this also requires disabling ISIC_PLACEHOLDER_IMAGES.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _ensure_exists(self, name):
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

    def open(self, name, *args, **kwargs):
        self._ensure_exists(name)
        return super().open(name, *args, **kwargs)

    def url(self, name: str, *args, **kwargs) -> str:
        self._ensure_exists(name)
        return super().url(name, *args, **kwargs)
