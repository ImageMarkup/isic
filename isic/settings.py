from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from composed_configuration import (
    ComposedConfiguration,
    ConfigMixin,
    DevelopmentBaseConfiguration,
    HerokuProductionBaseConfiguration,
    TestingBaseConfiguration,
)
from configurations import values
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.serializers import as_serializer_error


def drf_default_with_modifications_exception_handler(exc, ctx):
    # TODO: importing this at the top level causes weird errors in test cases with list
    # endpoints.
    from rest_framework.views import exception_handler

    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(as_serializer_error(exc))

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()

    if isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, ctx)

    # If unexpected error occurs (server error, etc.)
    if response is None:
        return response

    if isinstance(exc.detail, (list, dict)):
        response.data = {"detail": response.data}

    return response


def _oauth2_pkce_required(client_id):
    from oauth2_provider.models import get_application_model

    OAuth2Application = get_application_model()
    oauth_application = OAuth2Application.objects.get(client_id=client_id)
    # PKCE is only required for public clients, but express the logic this way to make it required
    # by default for any future new client_types
    return oauth_application.client_type != OAuth2Application.CLIENT_CONFIDENTIAL


class IsicMixin(ConfigMixin):
    WSGI_APPLICATION = "isic.wsgi.application"
    ROOT_URLCONF = "isic.urls"

    BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

    @staticmethod
    def mutate_configuration(configuration: ComposedConfiguration) -> None:
        # Install local apps first, to ensure any overridden resources are found first
        configuration.INSTALLED_APPS = [
            "isic.core.apps.CoreConfig",
            "isic.find.apps.FindConfig",
            "isic.login.apps.LoginConfig",
            "isic.ingest.apps.IngestConfig",
            "isic.stats.apps.StatsConfig",
            "isic.studies.apps.StudiesConfig",
        ] + configuration.INSTALLED_APPS

        # Install additional apps
        configuration.INSTALLED_APPS += [
            "s3_file_field",
            "nested_admin",
            "django_object_actions",
            "django_json_widget",
            "spurl",
            "widget_tweaks",
        ]

        # PASSWORD_HASHERS are ordered "best" to "worst", appending Girder last means
        # it will be upgraded on login.
        configuration.PASSWORD_HASHERS += ["isic.login.hashers.GirderPasswordHasher"]

        configuration.OAUTH2_PROVIDER.update(
            {
                # Discourse login does not support PKCE
                "PKCE_REQUIRED": _oauth2_pkce_required,
                "SCOPES": {
                    "identity": "Access to your basic profile information",
                    "image:read": "Read access to images",
                    "image:write": "Write access to images",
                },
                "DEFAULT_SCOPES": ["identity"],
                # Allow setting DJANGO_OAUTH_ALLOWED_REDIRECT_URI_SCHEMES to override this on the
                # sandbox instance.
                "ALLOWED_REDIRECT_URI_SCHEMES": values.ListValue(
                    ["http", "https"] if configuration.DEBUG else ["https"],
                    environ_name="OAUTH_ALLOWED_REDIRECT_URI_SCHEMES",
                    environ_prefix="DJANGO",
                    environ_required=False,
                    # Disable late_binding, to make this return a usable value (which is a list)
                    # immediately.
                    late_binding=False,
                ),
            }
        )

        configuration.TEMPLATES[0]["OPTIONS"]["context_processors"] += [
            "isic.core.context_processors.noindex",
            "isic.core.context_processors.sandbox_banner",
        ]

        configuration.REST_FRAMEWORK[
            "EXCEPTION_HANDLER"
        ] = "isic.settings.drf_default_with_modifications_exception_handler"
        configuration.REST_FRAMEWORK[
            "DEFAULT_PAGINATION_CLASS"
        ] = "isic.core.pagination.CursorWithCountPagination"

    AUTHENTICATION_BACKENDS = [
        "allauth.account.auth_backends.AuthenticationBackend",
        "isic.core.permissions.IsicObjectPermissionsBackend",
    ]

    ACCOUNT_SIGNUP_FORM_CLASS = "isic.login.forms.RealNameSignupForm"

    OAUTH2_PROVIDER_APPLICATION_MODEL = "core.IsicOAuthApplication"
    ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS = values.BooleanValue(False)

    ISIC_NOINDEX = values.BooleanValue(False)
    ISIC_SANDBOX_BANNER = values.BooleanValue(False)
    ISIC_ELASTICSEARCH_URI = values.SecretValue()
    ISIC_ELASTICSEARCH_INDEX = "isic"
    ISIC_GUI_URL = "https://www.isic-archive.com"
    ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = ISIC_GUI_URL
    ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = ISIC_GUI_URL
    ISIC_DATACITE_API_URL = values.Value("https://api.test.datacite.org")
    ISIC_DATACITE_USERNAME = values.Value(None)
    ISIC_DATACITE_PASSWORD = values.SecretValue(None)
    ISIC_GOOGLE_ANALYTICS_VIEW_IDS = [
        "183845203",  # ISIC Gallery
        "217814783",  # ISIC Challenge 2020
        "199577101",  # ISIC Challenge
    ]
    # This is technically a secret, but it's unset in sandbox so we don't want to make
    # it required.
    ISIC_GOOGLE_API_JSON_KEY = values.Value(None)

    CDN_LOG_BUCKET = values.Value()

    CELERY_WORKER_MAX_MEMORY_PER_CHILD = 256 * 1024

    CELERY_BEAT_SCHEDULE = {
        "collect-google-analytics-stats": {
            "task": "isic.stats.tasks.collect_google_analytics_metrics_task",
            "schedule": timedelta(hours=6),
        },
        "collect-image-download-stats": {
            "task": "isic.stats.tasks.collect_image_download_records_task",
            "schedule": timedelta(hours=2),
        },
        "sync-elasticsearch-index": {
            "task": "isic.core.tasks.sync_elasticsearch_index_task",
            "schedule": timedelta(hours=12),
        },
    }


class DevelopmentConfiguration(IsicMixin, DevelopmentBaseConfiguration):
    # Development-only settings
    SHELL_PLUS_IMPORTS = [
        "from isic.core.tasks import *",
        "from isic.ingest.tasks import *",
        "from isic.stats.tasks import *",
        "from isic.studies.tasks import *",
        "from django.core.files.uploadedfile import UploadedFile",
        "import pandas as pd",
        "from opensearchpy import OpenSearch",
        "from isic.core.search import *",
    ]
    SHELL_PLUS_PRINT_SQL_TRUNCATE = None
    RUNSERVER_PLUS_PRINT_SQL_TRUNCATE = None
    # Allow developers to run tasks synchronously for easy debugging
    CELERY_TASK_ALWAYS_EAGER = values.BooleanValue(False)
    CELERY_TASK_EAGER_PROPAGATES = values.BooleanValue(False)
    ISIC_DATACITE_DOI_PREFIX = "10.80222"
    MINIO_STORAGE_MEDIA_OBJECT_METADATA = {"Content-Disposition": "attachment"}

    ZIP_DOWNLOAD_SERVICE_URL = "http://localhost:4008"


class TestingConfiguration(IsicMixin, TestingBaseConfiguration):
    ISIC_ELASTICSEARCH_INDEX = "isic-testing"
    ISIC_DATACITE_USERNAME = None
    ISIC_DATACITE_PASSWORD = None
    CELERY_TASK_ALWAYS_EAGER = values.BooleanValue(False)
    CELERY_TASK_EAGER_PROPAGATES = values.BooleanValue(False)
    ISIC_DATACITE_DOI_PREFIX = "10.80222"
    ZIP_DOWNLOAD_SERVICE_URL = "http://service-url.test"


class HerokuProductionConfiguration(IsicMixin, HerokuProductionBaseConfiguration):
    ISIC_DATACITE_DOI_PREFIX = "10.34970"
    ISIC_ELASTICSEARCH_URI = values.SecretValue(environ_name="SEARCHBOX_URL", environ_prefix=None)

    AWS_CLOUDFRONT_KEY = values.SecretValue()
    AWS_CLOUDFRONT_KEY_ID = values.Value()
    AWS_S3_CUSTOM_DOMAIN = values.Value()
    DEFAULT_FILE_STORAGE = "isic.core.storage.CacheableCloudFrontStorage"

    AWS_S3_OBJECT_PARAMETERS = {"ContentDisposition": "attachment"}

    SENTRY_TRACES_SAMPLE_RATE = 0.01  # sample 1% of requests for performance monitoring

    ZIP_DOWNLOAD_SERVICE_URL = values.Value()
