import os

import dj_database_url

from ._docker import _AlwaysContains, _is_docker
from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "insecuresecret"  # noqa: S105

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "django"]
CORS_ORIGIN_REGEX_WHITELIST = [
    r"^https?://localhost:\d+$",
    r"^https?://127\.0\.0\.1:\d+$",
]

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ["DJANGO_DATABASE_URL"], conn_max_age=600, conn_health_checks=False
    )
}

# When in Docker, the bridge network sends requests from the host machine exclusively via a
# dedicated IP address. Since there's no way to determine the real origin address,
# consider any IP address (though actually this will only be the single dedicated address) to
# be internal. This relies on the host to set up appropriate firewalls for Docker, to prevent
# access from non-internal addresses.
INTERNAL_IPS = _AlwaysContains() if _is_docker() else ["127.0.0.1"]

CELERY_TASK_ACKS_LATE = False
CELERY_WORKER_CONCURRENCY = 1

DEBUG_TOOLBAR_CONFIG = {
    "RESULTS_CACHE_SIZE": 250,
    "PRETTIFY_SQL": False,
}

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # noqa: F405, RUF005

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["DJANGO_REDIS_URL"],
    }
}


SHELL_PLUS_IMPORTS = [
    "from django.core.files.uploadedfile import UploadedFile",
    "from isic.ingest.services.accession import *",
    "from isic.ingest.services.zip_upload import *",
    "from isic.core.dsl import *",
    "from isic.core.search import *",
    "from isic.core.tasks import *",
    "from isic.ingest.services.cohort import *",
    "from isic.ingest.tasks import *",
    "from isic.stats.tasks import *",
    "from isic.studies.tasks import *",
    "from opensearchpy import OpenSearch",
]
# Allow developers to run tasks synchronously for easy debugging
CELERY_TASK_ALWAYS_EAGER = os.environ.get("DJANGO_CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = os.environ.get("DJANGO_CELERY_TASK_EAGER_PROPAGATES", False)
ISIC_DATACITE_DOI_PREFIX = "10.80222"

ZIP_DOWNLOAD_SERVICE_URL = "http://localhost:4008"
ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = "insecurezipdownloadauthtoken"  # noqa: S105
# Requires CloudFront configuration
ZIP_DOWNLOAD_WILDCARD_URLS = False

MINIO_STORAGE_ENDPOINT = os.environ["DJANGO_MINIO_STORAGE_ENDPOINT"]
MINIO_STORAGE_USE_HTTPS = False
MINIO_STORAGE_ACCESS_KEY = os.environ["DJANGO_MINIO_STORAGE_ACCESS_KEY"]
MINIO_STORAGE_SECRET_KEY = os.environ["DJANGO_MINIO_STORAGE_SECRET_KEY"]
MINIO_STORAGE_MEDIA_URL = os.environ.get("DJANGO_MINIO_STORAGE_MEDIA_URL")
MINIO_STORAGE_AUTO_CREATE_MEDIA_BUCKET = True
MINIO_STORAGE_AUTO_CREATE_MEDIA_POLICY = "READ_WRITE"
MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}

STORAGES.update(  # noqa: F405
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.FixedMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": os.environ["DJANGO_STORAGE_BUCKET_NAME"],
                "presign_urls": True,
            },
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.minio.FixedMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": os.environ["DJANGO_SPONSORED_BUCKET_NAME"],
                "presign_urls": False,
            },
        },
    }
)

ISIC_PLACEHOLDER_IMAGES = True
# Use the MinioS3ProxyStorage for local development with ISIC_PLACEHOLDER_IMAGES
# set to False to view real images in development.
# STORAGES["default"]["BACKEND"] = (
#    "isic.core.storages.minio.MinioS3ProxyStorage"
# )

# Move the debug toolbar middleware after gzip middleware
# See https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#add-the-middleware
# Remove the middleware from the default location
MIDDLEWARE.remove("debug_toolbar.middleware.DebugToolbarMiddleware")
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.gzip.GZipMiddleware") + 1,
    "debug_toolbar.middleware.DebugToolbarMiddleware",
)
DEBUG_TOOLBAR_CONFIG = {
    # The default size often is too small, causing an inability to view queries
    "RESULTS_CACHE_SIZE": 250,
    # If this setting is True, large sql queries can cause the page to render slowly
    "PRETTIFY_SQL": False,
}

ISIC_JS_BROWSER_SYNC = True
