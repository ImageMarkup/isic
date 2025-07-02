from typing import cast

from botocore.config import Config

import sentry_sdk
import sentry_sdk.integrations.celery
import sentry_sdk.integrations.django
import sentry_sdk.integrations.logging
import sentry_sdk.integrations.pure_eval

from ._sentry_utils import get_sentry_performance_sample_rate
from .base import *

# Import these afterwards, to override
from resonant_settings.production.email import *
from resonant_settings.production.https import *
from resonant_settings.production.s3_storage import *

WSGI_APPLICATION = "isic.wsgi.application"

SECRET_KEY: str = env.str("DJANGO_SECRET_KEY")

# This only needs to be defined in production. Testing will add 'testserver'.
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", cast=str)

STORAGES.update(
    {
        "default": {
            "BACKEND": "isic.core.storages.s3.CacheableCloudFrontStorage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "custom_domain": cast(str, env.str("DJANGO_ISIC_STORAGE_CUSTOM_DOMAIN")),
                "cloudfront_key_id": cast(str, env.str("DJANGO_ISIC_STORAGE_CLOUDFRONT_KEY_ID")),
                "cloudfront_key": cast(str, env.str("DJANGO_ISIC_STORAGE_CLOUDFRONT_KEY")),
            },
        },
        "sponsored": {
            "BACKEND": "isic.core.storages.s3.PreventRenamingS3StaticStorage",
            "OPTIONS": {
                "bucket_name": cast(str, env.str("DJANGO_ISIC_SPONSORED_BUCKET_NAME")),
            },
        },
    }
)
# Settings for generating Storage URLs:
AWS_S3_OBJECT_PARAMETERS = {"ContentDisposition": "attachment"}
# Settings for internal Storage access:
AWS_S3_FILE_BUFFER_SIZE = 50 * 1024 * 1024  # 50MB
AWS_S3_CLIENT_CONFIG = Config(
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 5},
    signature_version=AWS_S3_SIGNATURE_VERSION,
)

ISIC_DATACITE_DOI_PREFIX = "10.34970"

ISIC_JS_SENTRY = True

# sentry_sdk is able to directly use environment variables like 'SENTRY_DSN', but prefix them
# with 'DJANGO_' to avoid avoiding conflicts with other Sentry-using services.
sentry_sdk.init(
    dsn=env.str("DJANGO_SENTRY_DSN", default=None),
    environment=env.str("DJANGO_SENTRY_ENVIRONMENT", default=None),
    release=env.str("DJANGO_SENTRY_RELEASE", default=None),
    integrations=[
        sentry_sdk.integrations.logging.LoggingIntegration(
            level=logging.INFO,
            event_level=logging.WARNING,
        ),
        sentry_sdk.integrations.django.DjangoIntegration(),
        sentry_sdk.integrations.celery.CeleryIntegration(monitor_beat_tasks=True),
        sentry_sdk.integrations.pure_eval.PureEvalIntegration(),
    ],
    # "project_root" defaults to the CWD, but for safety, don't assume that will be set correctly
    project_root=str(BASE_DIR),
    # Send traces for non-exception events too
    attach_stacktrace=True,
    # Submit request User info from Django
    send_default_pii=True,
    traces_sampler=get_sentry_performance_sample_rate,
    profiles_sampler=get_sentry_performance_sample_rate,
)
