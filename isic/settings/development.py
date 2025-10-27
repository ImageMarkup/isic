from typing import cast

import logging
from django_extensions.utils import InternalIPS
from minio_storage.policy import Policy

from .base import *

# Import these afterwards, to override
from resonant_settings.development.celery import *
from resonant_settings.development.debug_toolbar import *
from resonant_settings.development.minio_storage import *


INSTALLED_APPS += [
    "debug_toolbar",
    "django_browser_reload",
]
# Force WhiteNoice to serve static files, even when using 'manage.py runserver_plus'
staticfiles_index = INSTALLED_APPS.index("django.contrib.staticfiles")
INSTALLED_APPS.insert(staticfiles_index, "whitenoise.runserver_nostatic")

# Include Debug Toolbar middleware as early as possible in the list.
# However, it must come after any other middleware that encodes the response's content,
# such as GZipMiddleware.
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.gzip.GZipMiddleware") + 1,
    "debug_toolbar.middleware.DebugToolbarMiddleware",
)
# Should be listed after middleware that encode the response.
MIDDLEWARE += [
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

# DEBUG is not enabled for testing, to maintain parity with production.
# Also, do not directly reference DEBUG when toggling application features; it's more sustainable
# to add new settings as individual feature flags.
DEBUG = True

SECRET_KEY = "insecure-secret"

RUNSERVERPLUS_SERVER_ADDRESS_PORT: str | None = env.str(
    "DJANGO_RUNSERVERPLUS_SERVER_ADDRESS_PORT", default=None
)

# The ISIC ZIP download service will resolve "django" when running from Docker;
# Otherwise, this can be unset, as the default is ["localhost", "127.0.0.1"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "django"]

# This is typically only overridden when running from Docker.
INTERNAL_IPS = InternalIPS(env.list("DJANGO_INTERNAL_IPS", cast=str, default=["127.0.0.1"]))

STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.IsicMinioMediaStorage",
        },
        "sponsored": {
            # Using a "MediaStorage" will reuse most of the settings for the default storage
            # (auto-detected from env vars), but we override some distinct options.
            "BACKEND": "isic.core.storages.minio.IsicMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": cast(str, env.str("DJANGO_ISIC_SPONSORED_BUCKET_NAME")),
                "base_url": cast(
                    str | None, env.str("DJANGO_ISIC_SPONSORED_MEDIA_URL", default=None)
                ),
                # Make a public-readable bucket
                "auto_create_policy": True,
                "policy_type": Policy.read,
                # Don't sign any URLs
                "presign_urls": False,
            },
        },
    }
)
MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}

ISIC_FAKE_STORAGE: str | None = env.str("DJANGO_ISIC_FAKE_STORAGE", default=None)
if ISIC_FAKE_STORAGE == "proxy":
    STORAGES["default"]["BACKEND"] = "isic.core.storages.minio.S3ProxyMinioStorage"
    STORAGES["default"].setdefault("OPTIONS", {})["upstream_bucket_name"] = "isic-storage"

    STORAGES["sponsored"]["BACKEND"] = "isic.core.storages.minio.S3ProxyMinioStorage"
    STORAGES["sponsored"].setdefault("OPTIONS", {})["upstream_bucket_name"] = "isic-archive"
elif ISIC_FAKE_STORAGE == "placeholder":
    STORAGES["default"]["BACKEND"] = "isic.core.storages.minio.PlaceholderMinioStorage"
    STORAGES["sponsored"]["BACKEND"] = "isic.core.storages.minio.PlaceholderMinioStorage"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Expire cache entries immediately to promote better understanding of actual query performance
CACHES["default"]["TIMEOUT"] = 0
# cachalot sets its own expiration time, so it needs to be set to 0 as well
CACHALOT_TIMEOUT = 0

OAUTH2_PROVIDER["ALLOWED_REDIRECT_URI_SCHEMES"] = ["http", "https"]
# In development, always present the approval dialog
OAUTH2_PROVIDER["REQUEST_APPROVAL_PROMPT"] = "force"

SHELL_PLUS_IMPORTS = [
    "from django.core.files.storage import storages",
    "from django.core.files.uploadedfile import UploadedFile",
    "from isic.ingest.services.accession import *",
    "from isic.ingest.services.zip_upload import *",
    "from isic.core.dsl import *",
    "from isic.core.health import *",
    "from isic.core.search import *",
    "from isic.core.tasks import *",
    "from isic.ingest.services.cohort import *",
    "from isic.ingest.tasks import *",
    "from isic.stats.tasks import *",
    "from isic.studies.tasks import *",
]

# suppress noisy cache invalidation log messages
logging.getLogger("isic.core.signals").setLevel(logging.ERROR)
