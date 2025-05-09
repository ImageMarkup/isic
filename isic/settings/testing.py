import logging
from secrets import randbelow

from minio_storage.policy import Policy

from .base import *

# Import these afterwards, to override
from resonant_settings.testing.minio_storage import *

SECRET_KEY = "insecure-secret"

# Use a fast, insecure hasher to speed up tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "isic.login.hashers.GirderPasswordHasher",
]

STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedStaticFilesStorage"

MINIO_STORAGE_MEDIA_BUCKET_NAME = f"test-django-storage-{randbelow(1_000_000):06d}"
STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": f"test-django-sponsored-{randbelow(1_000_000):06d}",
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
