from secrets import randbelow

from .base import *

SECRET_KEY = "insecure-secret"

# Use a fast, insecure hasher to speed up tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

from resonant_settings.testing.minio_storage import *  # noqa: E402

STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": f"test-django-storage-{randbelow(1_000_000):06d}",
                "presign_urls": True,
            },
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioStorage",
            "OPTIONS": {
                "bucket_name": f"test-django-sponsored-{randbelow(1_000_000):06d}",
                "presign_urls": False,
            },
        },
    }
)
MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}

# Testing will set EMAIL_BACKEND to use the memory backend

# TODO: set these upstream instead?
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

ISIC_ELASTICSEARCH_IMAGES_INDEX = "test-isic-images"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "test-isic-lesions"
ISIC_USE_ELASTICSEARCH_COUNTS = False





# ISIC_ZIP_DOWNLOAD_SERVICE_URL = "http://service-url.test"
# ISIC_ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = "insecuretestzipdownloadauthtoken"

# suppress noisy cache invalidation log messages in testing
LOGGING["loggers"]["isic.core.signals"] = {"level": "ERROR"}
