import os

import dj_database_url

from .base import *  # noqa: F403

SECRET_KEY = "testingsecret"  # noqa: S105

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ["DJANGO_DATABASE_URL"], conn_max_age=600, conn_health_checks=False
    )
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ["DJANGO_REDIS_URL"],
    }
}

# Testing will add 'testserver' to ALLOWED_HOSTS
ALLOWED_HOSTS: list[str] = []

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_CONCURRENCY = None
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHALOT_ENABLED = True

ISIC_ELASTICSEARCH_IMAGES_INDEX = "test-isic-images"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "test-isic-lesions"

ISIC_DATACITE_DOI_PREFIX = "10.80222"
ZIP_DOWNLOAD_SERVICE_URL = "http://service-url.test"
ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = "insecuretestzipdownloadauthtoken"  # noqa: S105
ZIP_DOWNLOAD_WILDCARD_URLS = False

STORAGES["default"] = {"BACKEND": "isic.core.storages.minio.StringableMinioMediaStorage"}  # noqa: F405


MINIO_STORAGE_ENDPOINT = os.environ["DJANGO_MINIO_STORAGE_ENDPOINT"]
MINIO_STORAGE_USE_HTTPS = False
MINIO_STORAGE_ACCESS_KEY = os.environ["DJANGO_MINIO_STORAGE_ACCESS_KEY"]
MINIO_STORAGE_SECRET_KEY = os.environ["DJANGO_MINIO_STORAGE_SECRET_KEY"]
MINIO_STORAGE_MEDIA_BUCKET_NAME = "test-django-storage"
MINIO_STORAGE_AUTO_CREATE_MEDIA_BUCKET = True
MINIO_STORAGE_AUTO_CREATE_MEDIA_POLICY = "READ_WRITE"
MINIO_STORAGE_MEDIA_USE_PRESIGNED = True


# use md5 in testing for quicker user creation
PASSWORD_HASHERS.insert(0, "django.contrib.auth.hashers.MD5PasswordHasher")  # noqa: F405

# suppress noisy cache invalidation log messages in testing
LOGGING["loggers"]["isic.core.signals"] = {"level": "ERROR"}  # noqa: F405
