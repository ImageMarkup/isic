import logging
from secrets import randbelow
from typing import cast
from urllib.parse import ParseResult

from minio_storage.policy import Policy

from .base import *

# Import these afterwards, to override
from resonant_settings.development.minio_storage import *

SECRET_KEY = "insecure-secret"

# Use a fast, insecure hasher to speed up tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "isic.login.hashers.GirderPasswordHasher",
]

STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedStaticFilesStorage"

MINIO_STORAGE_MEDIA_BUCKET_NAME = f"test-django-storage-{randbelow(1_000_000):06d}"
isic_sponsored_bucket_name = f"test-django-sponsored-{randbelow(1_000_000):06d}"
isic_sponsored_media_url = cast(
    ParseResult | None, env.url("DJANGO_ISIC_SPONSORED_MEDIA_URL", default=None)
)
isic_sponsored_base_url = (
    # Form a URL with the sponsored bucket media URL host information,
    # but with the ephemeral testing bucket name.
    f"{isic_sponsored_media_url.scheme}://{isic_sponsored_media_url.netloc}"
    f"/{isic_sponsored_bucket_name}"
    if isic_sponsored_media_url
    else None
)
STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": isic_sponsored_bucket_name,
                "base_url": isic_sponsored_base_url,
                "auto_create_policy": True,
                "policy_type": Policy.read,
                "presign_urls": False,
            },
        },
    }
)
MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}

# Testing will set EMAIL_BACKEND to use the memory backend

# ISIC tests expect these to always be enabled, though they are optional in development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

ISIC_ELASTICSEARCH_IMAGES_INDEX = "test-isic-images"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "test-isic-lesions"
ISIC_USE_ELASTICSEARCH_COUNTS = False

ISIC_ZIP_DOWNLOAD_WILDCARD_URLS = False

# suppress noisy cache invalidation log messages
logging.getLogger("isic.core.signals").setLevel(logging.ERROR)
