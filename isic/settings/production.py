import logging
import os

from botocore.config import Config
import dj_email_url
from django_cache_url import BACKENDS
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration

from ._utils import _get_sentry_performance_sample_rate, string_to_bool, string_to_list
from .base import *  # noqa: F403

# This is an unfortunate monkeypatching of django_cache_url to support an old version
# of django-redis on a newer version of django.
# See https://github.com/noripyt/django-cachalot/issues/222 for fixing this.
BACKENDS["redis"] = BACKENDS["rediss"] = "django_redis.cache.RedisCache"


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

CELERY_BROKER_URL = os.environ["CLOUDAMQP_URL"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_CONCURRENCY = None

ALLOWED_HOSTS = string_to_list(os.environ["DJANGO_ALLOWED_HOSTS"])

# Enable HSTS
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
# This is already False by default, but it's important to ensure HSTS is not forced on other
# subdomains which may have different HTTPS practices.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
# This is already False by default, but per https://hstspreload.org/#opt-in, projects should
# opt-in to preload by overriding this setting. Additionally, all subdomains must have HSTS to
# register for preloading.
SECURE_HSTS_PRELOAD = False


SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# https://help.heroku.com/J2R1S4T8/can-heroku-force-an-application-to-use-ssl-tls
SECURE_PROXY_SSL_HEADER: tuple[str, str] | None = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {
    "default": dj_database_url.config(  # noqa: F405
        default=os.environ["DATABASE_URL"],
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}

# Email
email_config = dj_email_url.config(env="DJANGO_EMAIL_URL")
EMAIL_FILE_PATH = email_config["EMAIL_FILE_PATH"]
EMAIL_HOST_USER = email_config["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = email_config["EMAIL_HOST_PASSWORD"]
EMAIL_HOST = email_config["EMAIL_HOST"]
EMAIL_PORT = email_config["EMAIL_PORT"]
EMAIL_BACKEND = email_config["EMAIL_BACKEND"]
EMAIL_USE_TLS = email_config["EMAIL_USE_TLS"]
EMAIL_USE_SSL = email_config["EMAIL_USE_SSL"]
EMAIL_TIMEOUT = email_config["EMAIL_TIMEOUT"]

# Set both settings from DJANGO_DEFAULT_FROM_EMAIL
DEFAULT_FROM_EMAIL = os.environ["DJANGO_DEFAULT_FROM_EMAIL"]
SERVER_EMAIL = os.environ["DJANGO_DEFAULT_FROM_EMAIL"]


sentry_sdk.init(
    # If a "dsn" is not explicitly passed, sentry_sdk will attempt to find the DSN in
    # the SENTRY_DSN environment variable; however, by pulling it from an explicit
    # setting, it can be overridden by downstream project settings.
    dsn=os.environ["DJANGO_SENTRY_DSN"],
    environment=os.environ["DJANGO_SENTRY_ENVIRONMENT"],
    # release=settings.SENTRY_RELEASE,
    integrations=[
        LoggingIntegration(level=logging.INFO, event_level=logging.WARNING),
        DjangoIntegration(),
        CeleryIntegration(monitor_beat_tasks=True),
        PureEvalIntegration(),
    ],
    in_app_include=["isic"],
    # Send traces for non-exception events too
    attach_stacktrace=True,
    # Submit request User info from Django
    send_default_pii=True,
    traces_sampler=_get_sentry_performance_sample_rate,
    profiles_sampler=_get_sentry_performance_sample_rate,
)


# This may be provided by https://github.com/ianpurvis/heroku-buildpack-version or similar
# The commit SHA is the preferred release tag for Git-based projects:
# https://docs.sentry.io/platforms/python/configuration/releases/#bind-the-version

# SENTRY_RELEASE = values.Value(
#     None,
#     environ_name="SOURCE_VERSION",
#     environ_prefix=None,
# )

ISIC_DATACITE_DOI_PREFIX = "10.34970"
ISIC_ELASTICSEARCH_URI = os.environ["SEARCHBOX_URL"]
ISIC_USE_ELASTICSEARCH_COUNTS = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["STACKHERO_REDIS_URL_TLS"],
    }
}

CACHALOT_ENABLED = True

AWS_CLOUDFRONT_KEY = os.environ["DJANGO_AWS_CLOUDFRONT_KEY"]
AWS_CLOUDFRONT_KEY_ID = os.environ["DJANGO_AWS_CLOUDFRONT_KEY_ID"]
AWS_S3_CUSTOM_DOMAIN = os.environ["DJANGO_AWS_S3_CUSTOM_DOMAIN"]

AWS_S3_OBJECT_PARAMETERS = {"ContentDisposition": "attachment"}

AWS_S3_FILE_BUFFER_SIZE = 50 * 1024 * 1024  # 50MB

SENTRY_TRACES_SAMPLE_RATE = 0.01  # sample 1% of requests for performance monitoring

ZIP_DOWNLOAD_SERVICE_URL = os.environ["DJANGO_ZIP_DOWNLOAD_SERVICE_URL"]
ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = os.environ["DJANGO_ZIP_DOWNLOAD_BASIC_AUTH_TOKEN"]
ZIP_DOWNLOAD_WILDCARD_URLS = True


STORAGES["default"] = {"BACKEND": "isic.core.storages.s3.CacheableCloudFrontStorage"}  # noqa: F405


# This exact environ_name is important, as direct use of Boto will also use it
AWS_S3_REGION_NAME = os.environ["AWS_DEFAULT_REGION"]
AWS_S3_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_S3_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_STORAGE_BUCKET_NAME = os.environ["DJANGO_STORAGE_BUCKET_NAME"]

# It's critical to use the v4 signature;
# it isn't the upstream default only for backwards compatability reasons.
AWS_S3_SIGNATURE_VERSION = "s3v4"

AWS_S3_MAX_MEMORY_SIZE = 5 * 1024 * 1024
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_EXPIRE = 3600 * 6  # 6 hours

AWS_S3_CLIENT_CONFIG = Config(
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 5},
    signature_version=AWS_S3_SIGNATURE_VERSION,
)

ISIC_GOOGLE_API_JSON_KEY = os.environ.get("ISIC_GOOGLE_API_JSON_KEY")

ISIC_NOINDEX = string_to_bool(os.environ["DJANGO_ISIC_NOINDEX"])
ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS = string_to_bool(
    os.environ["DJANGO_ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS"]
)
ISIC_SANDBOX_BANNER = string_to_bool(os.environ["DJANGO_ISIC_SANDBOX_BANNER"])

CDN_LOG_BUCKET = os.environ["DJANGO_CDN_LOG_BUCKET"]
