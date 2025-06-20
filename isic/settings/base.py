from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from celery.schedules import crontab
import django_stubs_ext
from environ import Env
from resonant_settings.allauth import *
from resonant_settings.celery import *
from resonant_settings.django import *
from resonant_settings.django_extensions import *
from resonant_settings.logging import *
from resonant_settings.oauth_toolkit import *

if TYPE_CHECKING:
    from urllib.parse import ParseResult


django_stubs_ext.monkeypatch()

env = Env()

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

ROOT_URLCONF = 'isic.urls'

INSTALLED_APPS = [
    # Install local apps first, to ensure any overridden resources are found first
    "isic.core.apps.CoreConfig",
    "isic.find.apps.FindConfig",
    "isic.ingest.apps.IngestConfig",
    "isic.login.apps.LoginConfig",
    "isic.stats.apps.StatsConfig",
    "isic.studies.apps.StudiesConfig",
    "isic.zip_download.apps.ZipDownloadConfig",
    # Apps with overrides
    'auth_style',
    'resonant_settings.allauth_support',
    # Everything else
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    "cachalot",
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.postgres',
    'django.contrib.sessions',
    "django.contrib.sitemaps",
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django_extensions',
    'django_filters',
    "markdownify",
    # Forces Swagger to be served locally, so it can be overridden
    "ninja",
    'oauth2_provider',
    'resonant_utils',
    's3_file_field',
    "widget_tweaks",
]

MIDDLEWARE = [
    # CorsMiddleware must be added before other response-generating middleware,
    # so it can potentially add CORS headers to those responses too.
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
# TODO: this ordering didn't match Django's
    # WhiteNoiseMiddleware must be directly after SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # GZipMiddleware can be after WhiteNoiseMiddleware, as WhiteNoise performs its own compression
    "django.middleware.gzip.GZipMiddleware",


"isic.middleware.UserTypeTagMiddleware",


    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
# Insert the ExemptBearerAuthFromCSRFMiddleware just before the CsrfViewMiddleware
"isic.middleware.ExemptBearerAuthFromCSRFMiddleware",
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# Internal datetimes are timezone-aware, so this only affects rendering and form input
TIME_ZONE = 'UTC'

DATABASES = {
    'default': {
        **env.db_url('DJANGO_DATABASE_URL', engine='django.db.backends.postgresql'),
        'CONN_MAX_AGE': timedelta(minutes=10).total_seconds(),
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STORAGES = {
    # Inject the default storage in particular run configurations
    'default': None,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

STATIC_ROOT = BASE_DIR / 'staticfiles'
# Django staticfiles auto-creates any intermediate directories, but do so here to prevent warnings.
STATIC_ROOT.mkdir(exist_ok=True)

# Django's docs suggest that STATIC_URL should be a relative path,
# for convenience serving a site on a subpath.
STATIC_URL = 'static/'

# Make Django and Allauth redirects consistent, but both may be changed.
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

CORS_ALLOWED_ORIGINS: list[str] = env.list('DJANGO_CORS_ALLOWED_ORIGINS', cast=str, default=[])
CORS_ALLOWED_ORIGIN_REGEXES: list[str] = env.list(
    'DJANGO_CORS_ALLOWED_ORIGIN_REGEXES', cast=str, default=[]
)

PASSWORD_HASHERS += [
    # Some very old accounts use this hash
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    # PASSWORD_HASHERS are ordered "best" to "worst", appending Girder last means
    # it will be upgraded on login.
    "isic.login.hashers.GirderPasswordHasher",
]

CELERY_BEAT_SCHEDULE = {
    "collect-google-analytics-stats": {
        "task": "isic.stats.tasks.collect_google_analytics_metrics_task",
        "schedule": timedelta(hours=6),
    },
    "sync-elasticsearch-index": {
        "task": "isic.core.tasks.sync_elasticsearch_indices_task",
        "schedule": crontab(minute="0", hour="0"),
    },
    "prune-expired-oauth-tokens": {
        "task": "isic.core.tasks.prune_expired_oauth_tokens",
        "schedule": crontab(minute="0", hour="0"),
    },
    "refresh-materialized-view-collection-counts": {
        "task": "isic.core.tasks.refresh_materialized_view_collection_counts_task",
        "schedule": crontab(minute="*/15", hour="*"),
        "options": {
            # to avoid overcomputing, the message should expire 60 seconds after created
            "expires": 60
        },
    },
}
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 256 * 1024

CACHES = {
    # use django-redis instead of the builtin backend. the builtin redis backend
    # doesn't support deleting keys by prefix, which is important for invalidating
    # specific cache keys. this isn't on the roadmap for django, see
    # https://code.djangoproject.com/ticket/35039#comment:1.
    "default": env.db_url("DJANGO_CACHE_URL", engine="django_redis.cache.RedisCache"),
}
DJANGO_REDIS_SCAN_ITERSIZE = 1_000
CACHALOT_CACHE_ITERATORS = False
# This seems like an essential setting for correctness, see
# https://github.com/noripyt/django-cachalot/issues/266
CACHALOT_FINAL_SQL_CHECK = True

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

OAUTH2_PROVIDER.update(
    {
        # PKCE_REQUIRED is on by default in oauth-toolkit >= 2.0
        "PKCE_REQUIRED": True,
        # Normally, "http" would only be allowed in development, but local developers
        # of the Gallery are allowed to authenticate against the production site
        "ALLOWED_REDIRECT_URI_SCHEMES": ['http', 'https'],
        "SCOPES": {
            "identity": "Access to your basic profile information",
            "image:read": "Read access to images",
            "image:write": "Write access to images",
        },
        "DEFAULT_SCOPES": ["identity"],
    }
)
OAUTH2_PROVIDER_APPLICATION_MODEL = "core.IsicOAuthApplication"

ISIC_ELASTICSEARCH_URL = env.str("DJANGO_ISIC_ELASTICSEARCH_URL")
ISIC_ELASTICSEARCH_IMAGES_INDEX = "isic"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "isic-lesions"
# This is an unfortunate feature flag that lets us disable this feature in testing,
# where having a permanently available ES index which is updated consistently in real
# time is too difficult. We hedge by having tests that verify our counts are correct
# with both methods.
ISIC_USE_ELASTICSEARCH_COUNTS = True

ISIC_DATACITE_API_URL: ParseResult | None = env.url("DJANGO_ISIC_DATACITE_API_URL", default=None)
# These are the default styles with their proper names that are used by the
# DataCite GUI. The full list of supported styles is at https://citation.doi.org/.
ISIC_DATACITE_CITATION_STYLES: dict[str, str] = {
    "apa": "APA",
    "harvard-cite-them-right": "Harvard",
    "modern-language-association": "MLA",
    "vancouver": "Vancouver",
    "chicago-fullnote-bibliography": "Chicago",
    "ieee": "IEEE",
}
ISIC_DATACITE_DOI_PREFIX = "10.80222"

ISIC_GOOGLE_API_JSON_KEY: dict | None = env.json('DJANGO_ISIC_GOOGLE_API_JSON_KEY', default=None)
ISIC_GOOGLE_ANALYTICS_PROPERTY_IDS = [
    "377090260",  # ISIC Home
    "360152967",  # ISIC Gallery
    "368050084",  # ISIC Challenge 2020
    "440566058",  # ISIC Challenge 2024
    "360125792",  # ISIC Challenge
    "265191179",  # ISIC API
    "265233311",  # ISDIS
]

ISIC_ZIP_DOWNLOAD_SERVICE_URL = env.url("DJANGO_ISIC_ZIP_DOWNLOAD_SERVICE_URL", default=None)
ISIC_ZIP_DOWNLOAD_BASIC_AUTH_TOKEN = env.str("DJANGO_ISIC_ZIP_DOWNLOAD_BASIC_AUTH_TOKEN", default=None)
ISIC_ZIP_DOWNLOAD_WILDCARD_URLS = False

ISIC_CDN_LOG_BUCKET: str | None = env.str("DJANGO_ISIC_CDN_LOG_BUCKET", default=None)

TEMPLATES[0]["OPTIONS"]["context_processors"] += [  # type: ignore[index]
    "isic.core.context_processors.placeholder_images",
    "isic.core.context_processors.js_sentry",
    "isic.core.context_processors.citation_styles",
]
ISIC_PLACEHOLDER_IMAGES = False
ISIC_JS_SENTRY = False















ACCOUNT_SIGNUP_FORM_CLASS = "resonant_utils.allauth.FullNameSignupForm"



AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
    "isic.core.permissions.IsicObjectPermissionsBackend",
]
# opensearch logs every single request, which is too verbose
LOGGING["loggers"]["elastic_transport"] = {"level": "WARNING"}  # noqa: F405
