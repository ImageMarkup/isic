from django_extensions.utils import InternalIPS

from .base import *

# Import these afterwards, to override
from resonant_settings.development.debug_toolbar import *  # noqa: E402,I001

SHELL_PLUS_IMPORTS = [
    "from django.core.files.storage import storages",
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
]

from resonant_settings.development.celery import *  # noqa: E402,I001

# Allow developers to run tasks synchronously for easy debugging
CELERY_TASK_ALWAYS_EAGER = env.bool("DJANGO_CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = env.bool("DJANGO_CELERY_TASK_EAGER_PROPAGATES", False)

INSTALLED_APPS += [
    'debug_toolbar',
    'django_browser_reload',
    'django_extensions',
]
# Force WhiteNoice to serve static files, even when using 'manage.py runserver_plus'
staticfiles_index = INSTALLED_APPS.index('django.contrib.staticfiles')
INSTALLED_APPS.insert(staticfiles_index, 'whitenoise.runserver_nostatic')

# Include Debug Toolbar middleware as early as possible in the list.
# However, it must come after any other middleware that encodes the response's content,
# such as GZipMiddleware.
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.gzip.GZipMiddleware") + 1,
    'debug_toolbar.middleware.DebugToolbarMiddleware'
)
# Should be listed after middleware that encode the response.
MIDDLEWARE += [
    'django_browser_reload.middleware.BrowserReloadMiddleware',
]

# DEBUG is not enabled for testing, to maintain parity with production.
# Also, do not directly reference DEBUG when toggling application features; it's more sustainable
# to add new settings as individual feature flags.
DEBUG = True

SECRET_KEY = 'insecure-secret'

# The ISIC ZIP download service will resolve "django" when running from Docker;
# Otherwise, this can be unset, as the default is ["localhost", "127.0.0.1"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "django"]

# This is typically only overridden when running from Docker.
INTERNAL_IPS = InternalIPS(
    env.list('DJANGO_INTERNAL_IPS', cast=str, default=['127.0.0.1'])
)
CORS_ALLOWED_ORIGIN_REGEXES = env.list(
    'DJANGO_CORS_ALLOWED_ORIGIN_REGEXES',
    cast=str,
    default=[r'^http://localhost:\d+$', r'^http://127\.0\.0\.1:\d+$'],
)

from resonant_settings.testing.minio_storage import *

STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioMediaStorage",
            "OPTIONS": {
                "bucket_name": MINIO_STORAGE_MEDIA_BUCKET_NAME,
                "presign_urls": True,
            },
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.minio.PreventRenamingMinioStorage",
            "OPTIONS": {
                "bucket_name": env.str("DJANGO_ISIC_SPONSORED_BUCKET_NAME"),
                "presign_urls": False,
            },
        },
    }
)
MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}
# Use the MinioS3ProxyStorage for local development with ISIC_PLACEHOLDER_IMAGES
# set to False to view real images in development.
# STORAGES["default"]["BACKEND"] = "isic.core.storages.minio.MinioS3ProxyStorage"
# STORAGES["default"]["OPTIONS"]["upstream_bucket_name"] = "isic-storage"

# STORAGES["sponsored"]["BACKEND"] = "isic.core.storages.minio.MinioS3ProxyStorage"
# STORAGES["sponsored"]["OPTIONS"]["upstream_bucket_name"] = "isic-archive"
ISIC_PLACEHOLDER_IMAGES = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Expire cache entries immediately to promote better understanding of actual query performance
CACHES["default"]["TIMEOUT"] = 0

# In development, always present the approval dialog
OAUTH2_PROVIDER['REQUEST_APPROVAL_PROMPT'] = 'force'





# TODO: enable browser reload?


# ISIC_ZIP_DOWNLOAD_SERVICE_URL = "http://localhost:4008"
ISIC_ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = "insecurezipdownloadauthtoken"
