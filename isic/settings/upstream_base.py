import os

import dj_database_url

from ._logging import _filter_favicon_requests, _filter_static_requests
from ._utils import string_to_list

# Login/auth
LOGIN_REDIRECT_URL = "/"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# The sites framework requires this to be set.
# In the unlikely case where a database's pk sequence for the django_site table is not reset,
# the default site object could have a different pk. Then this will need to be overridden
# downstream.
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # Django's built-in ModelBackend is not necessary, since all users will be
    # authenticated by their email address
    "allauth.account.auth_backends.AuthenticationBackend",
]

# see configuration documentation at
#   https://django-allauth.readthedocs.io/en/latest/configuration.html

# Require email verification, but this can be overridden
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# Make Django and Allauth redirects consistent, but both may be overridden
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Use email as the identifier for login
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False

# Set the username as the email
ACCOUNT_ADAPTER = "isic.settings._allauth.EmailAsUsernameAccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# Quality of life improvements, but may not work if the browser is closed
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True

# These will permit GET requests to mutate the user state, but significantly improve usability
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

# This will likely become the default in the future, but enable it now
ACCOUNT_PRESERVE_USERNAME_CASING = False

OAUTH2_PROVIDER = {
    "PKCE_REQUIRED": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    # Don't require users to re-approve scopes each time
    "REQUEST_APPROVAL_PROMPT": "auto",
    # ERROR_RESPONSE_WITH_SCOPES is only used with the "permission_classes" helpers for scopes.
    # If the scope itself is confidential, this could leak information. but the usability
    # benefit is probably worth it.
    "ERROR_RESPONSE_WITH_SCOPES": True,
    # Allow 5 minutes for a flow to exchange an auth code for a token. This is typically
    # 60 seconds but out-of-band flows may take a bit longer. A maximum of 10 minutes is
    # recommended: https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.2.
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": 5 * 60,
    # Django can persist logins for longer than this via cookies,
    # but non-refreshing clients will need to redirect to Django's auth every 24 hours.
    "ACCESS_TOKEN_EXPIRE_SECONDS": 24 * 60 * 60,
    # This allows refresh tokens to eventually be removed from the database by
    # "manage.py cleartokens". This value is not actually enforced when refresh tokens are
    # checked, but it can be assumed that all clients will need to redirect to Django's auth
    # every 30 days.
    "REFRESH_TOKEN_EXPIRE_SECONDS": 30 * 24 * 60 * 60,
}

# Celery
CELERY_BROKER_CONNECTION_TIMEOUT = 30
CELERY_BROKER_HEARTBEAT = None
CELERY_BROKER_POOL_LIMIT = 1
CELERY_BROKER_URL = os.environ.get("DJANGO_CELERY_BROKER_URL", "amqp://localhost:5672/")
CELERY_EVENT_QUEUE_EXPIRES = 60
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = True
CELERY_TASK_REJECT_ON_WORKER_LOST = False
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
CELERY_WORKER_CONCURRENCY = 1
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# CORS
CORS_ALLOW_CREDENTIALS = False
CORS_ORIGIN_WHITELIST = string_to_list(os.environ.get("DJANGO_CORS_ORIGIN_WHITELIST", ""))
CORS_ORIGIN_REGEX_WHITELIST = string_to_list(
    os.environ.get("DJANGO_CORS_ORIGIN_REGEX_WHITELIST", "")
)

# Database config
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ["DJANGO_DATABASE_URL"], conn_max_age=600, conn_health_checks=False
    )
}

# Logging config
LOGGING = {
    "version": 1,
    # Replace existing logging configuration
    "incremental": False,
    # This redefines all of Django's declared loggers, but most loggers are implicitly
    # declared on usage, and should not be disabled. They often propagate their output
    # to the root anyway.
    "disable_existing_loggers": False,
    "formatters": {"rich": {"datefmt": "[%X]"}},
    "filters": {
        "filter_favicon_requests": {
            "()": "django.utils.log.CallbackFilter",
            "callback": _filter_favicon_requests,
        },
        "filter_static_requests": {
            "()": "django.utils.log.CallbackFilter",
            "callback": _filter_static_requests,
        },
    },
    "handlers": {
        "console": {
            "class": "rich.logging.RichHandler",
            "formatter": "rich",
            "filters": ["filter_favicon_requests", "filter_static_requests"],
        },
    },
    # Existing loggers actually contain direct (non-string) references to existing handlers,
    # so after redefining handlers, all existing loggers must be redefined too
    "loggers": {
        # Configure the root logger to output to the console
        "": {"level": "INFO", "handlers": ["console"], "propagate": False},
        # Django defines special configurations for the "django" and "django.server" loggers,
        # but we will manage all content at the root logger instead, so reset those
        # configurations.
        "django": {
            "handlers": [],
            "level": "NOTSET",
            "propagate": True,
        },
        "django.server": {
            "handlers": [],
            "level": "NOTSET",
            "propagate": True,
        },
    },
}

# Storage config
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Misc
STATIC_URL = "static/"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]
TIME_ZONE = "UTC"
USE_TZ = True
