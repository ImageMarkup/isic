from datetime import timedelta
import os
from pathlib import Path
from typing import Any

from celery.schedules import crontab
import django_stubs_ext

from .upstream_base import *  # noqa: F403

django_stubs_ext.monkeypatch()


def _oauth2_pkce_required(client_id):
    from oauth2_provider.models import get_application_model

    OAuth2Application = get_application_model()  # noqa: N806
    oauth_application = OAuth2Application.objects.get(client_id=client_id)
    # PKCE is only required for public clients, but express the logic this way to make it required
    # by default for any future new client_types
    return oauth_application.client_type != OAuth2Application.CLIENT_CONFIDENTIAL


RAISE_MISSING_TEMPLATE_VARIABLES = False

LOGGING["filters"]["missing_variable_error"] = {  # noqa: F405
    "()": "isic.core.templating.MissingVariableErrorFilter",
}

LOGGING["loggers"]["django.template"] = {  # noqa: F405
    "level": "DEBUG",
    "filters": ["missing_variable_error"],
}

# PASSWORD_HASHERS are ordered "best" to "worst", appending Girder last means
# it will be upgraded on login.
PASSWORD_HASHERS += ["isic.login.hashers.GirderPasswordHasher"]  # noqa: F405

AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
    "isic.core.permissions.IsicObjectPermissionsBackend",
]

ACCOUNT_SIGNUP_FORM_CLASS = "isic.login.forms.RealNameSignupForm"

OAUTH2_PROVIDER.update(  # noqa: F405
    {
        # Discourse login does not support PKCE
        "PKCE_REQUIRED": _oauth2_pkce_required,
        "SCOPES": {
            "identity": "Access to your basic profile information",
            "image:read": "Read access to images",
            "image:write": "Write access to images",
        },
        "DEFAULT_SCOPES": ["identity"],
    }
)
OAUTH2_PROVIDER_APPLICATION_MODEL = "core.IsicOAuthApplication"

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
}

# This seems like an essential setting for correctness, see
# https://github.com/noripyt/django-cachalot/issues/266.
CACHALOT_FINAL_SQL_CHECK = True

# Retry connections in case rabbit isn't immediately running
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
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
        "task": "isic.core.tasks.sync_elasticsearch_indices_task",
        "schedule": crontab(minute="0", hour="0"),
    },
    "prune-expired-oauth-tokens": {
        "task": "isic.core.tasks.prune_expired_oauth_tokens",
        "schedule": crontab(minute="0", hour="0"),
    },
}

# Install local apps first, to ensure any overridden resources are found first
INSTALLED_APPS = [
    # auth_style needs to come first to ensure it can override templates
    "auth_style",
    "allauth.account",
    "allauth.socialaccount",
    "allauth",
    "cachalot",
    "corsheaders",
    "django_extensions",
    "django_json_widget",
    "django_object_actions",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.sites",
    "whitenoise.runserver_nostatic",  # should be immediately before staticfiles app
    "django.contrib.staticfiles",
    "girder_utils",
    "isic.core.apps.CoreConfig",
    "isic.find.apps.FindConfig",
    "isic.ingest.apps.IngestConfig",
    "isic.login.apps.LoginConfig",
    "isic.stats.apps.StatsConfig",
    "isic.studies.apps.StudiesConfig",
    "isic.zip_download.apps.ZipDownloadConfig",
    "markdownify.apps.MarkdownifyConfig",
    "ninja",  # required because we overwrite ninja/swagger.html
    "oauth2_provider",
    "s3_file_field",
    "widget_tweaks",
]

# Middleware
MIDDLEWARE = [
    "isic.middleware.UserTypeTagMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Insert the ExemptBearerAuthFromCSRFMiddleware just before the CsrfViewMiddleware
    "isic.middleware.ExemptBearerAuthFromCSRFMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

MARKDOWNIFY = {
    "default": {
        # see https://bleach.readthedocs.io/en/latest/clean.html#allowed-tags-tags
        "WHITELIST_TAGS": [
            "a",
            "b",
            "blockquote",
            "em",
            "i",
            "li",
            "ol",
            "p",
            "strong",
            "ul",
            "h1",
            "h2",
            "h3",
        ]
    }
}

# django-extensions
RUNSERVER_PLUS_PRINT_SQL_TRUNCATE = None
SHELL_PLUS_PRINT_SQL = True
SHELL_PLUS_PRINT_SQL_TRUNCATE = None

# Misc
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
STATIC_ROOT = BASE_DIR / "staticfiles"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
WSGI_APPLICATION = "isic.wsgi.application"
ROOT_URLCONF = "isic.urls"

TEMPLATES[0]["OPTIONS"]["context_processors"] += [  # type: ignore[index]  # noqa: F405
    "isic.core.context_processors.noindex",
    "isic.core.context_processors.sandbox_banner",
    "isic.core.context_processors.placeholder_images",
    "isic.core.context_processors.js_browser_sync",
    "isic.core.context_processors.js_sentry",
]

# ISIC specific settings
# This is an unfortunate feature flag that lets us disable this feature in testing,
# where having a permanently available ES index which is updated consistently in real
# time is too difficult. We hedge by having tests that verify our counts are correct
# with both methods.
ISIC_USE_ELASTICSEARCH_COUNTS = False

ELASTICSEARCH_URL = os.environ.get("DJANGO_ELASTICSEARCH_URL")
ISIC_ELASTICSEARCH_IMAGES_INDEX = "isic"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "isic-lesions"
ISIC_GUI_URL = "https://www.isic-archive.com/"
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = ISIC_GUI_URL
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = ISIC_GUI_URL

ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS = False

ISIC_NOINDEX = False
ISIC_SANDBOX_BANNER = False
ISIC_PLACEHOLDER_IMAGES = False
ISIC_JS_BROWSER_SYNC = False
ISIC_JS_SENTRY = False

ISIC_DATACITE_API_URL = os.environ.get(
    "DJANGO_ISIC_DATACITE_API_URL", "https://api.test.datacite.org"
)
ISIC_DATACITE_USERNAME: Any = None
ISIC_DATACITE_PASSWORD: Any = None
ISIC_GOOGLE_ANALYTICS_PROPERTY_IDS = [
    "377090260",  # ISIC Home
    "360152967",  # ISIC Gallery
    "368050084",  # ISIC Challenge 2020
    "440566058",  # ISIC Challenge 2024
    "360125792",  # ISIC Challenge
    "265191179",  # ISIC API
    "265233311",  # ISDIS
]

ISIC_GOOGLE_API_JSON_KEY: str | None = None

CDN_LOG_BUCKET: Any = None


AWS_CLOUDFRONT_KEY: Any
AWS_CLOUDFRONT_KEY_ID: Any
AWS_S3_CUSTOM_DOMAIN: Any
