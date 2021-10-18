from __future__ import annotations

from pathlib import Path

from composed_configuration import (
    ComposedConfiguration,
    ConfigMixin,
    DevelopmentBaseConfiguration,
    HerokuProductionBaseConfiguration,
    ProductionBaseConfiguration,
    TestingBaseConfiguration,
)
from configurations import values


class IsicMixin(ConfigMixin):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

    @staticmethod
    def before_binding(configuration: ComposedConfiguration) -> None:
        # Install local apps first, to ensure any overridden resources are found first
        configuration.INSTALLED_APPS = [
            'isic.core.apps.CoreConfig',
            'isic.login.apps.LoginConfig',
            'isic.ingest.apps.IngestConfig',
            'isic.studies.apps.StudiesConfig',
            'isic.discourse_sso.apps.DiscourseSSOConfig',
        ] + configuration.INSTALLED_APPS

        # Install additional apps
        configuration.INSTALLED_APPS += [
            's3_file_field',
            'nested_admin',
            'django_object_actions',
            'django_json_widget',
        ]

        # PASSWORD_HASHERS are ordered "best" to "worst", appending Girder last means
        # it will be upgraded on login.
        configuration.PASSWORD_HASHERS += ['isic.login.backends.GirderPasswordHasher']

        configuration.OAUTH2_PROVIDER.update(
            {
                'SCOPES': {
                    'identity': 'Access to your basic profile information',
                    'image:read': 'Read access to images',
                    'image:write': 'Write access to images',
                },
                'DEFAULT_SCOPES': ['identity'],
                # Allow setting DJANGO_OAUTH_ALLOWED_REDIRECT_URI_SCHEMES to override this on the
                # sandbox instance.
                'ALLOWED_REDIRECT_URI_SCHEMES': values.ListValue(
                    ['http', 'https'] if configuration.DEBUG else ['https'],
                    environ_name='OAUTH_ALLOWED_REDIRECT_URI_SCHEMES',
                    environ_prefix='DJANGO',
                    environ_required=False,
                    # Disable late_binding, to make this return a usable value (which is a list)
                    # immediately.
                    late_binding=False,
                ),
            }
        )

    AUTHENTICATION_BACKENDS = [
        'isic.login.backends.GirderBackend',
        'allauth.account.auth_backends.AuthenticationBackend',
        'isic.core.permissions.IsicObjectPermissionsBackend',
    ]

    ACCOUNT_SIGNUP_FORM_CLASS = 'isic.login.forms.RealNameSignupForm'

    ISIC_DISCOURSE_SSO_SECRET = values.Value(None)
    ISIC_DISCOURSE_SSO_FAIL_URL = 'https://forum.isic-archive.com/'
    ISIC_MONGO_URI = values.SecretValue()
    ISIC_ELASTICSEARCH_URI = values.SecretValue()
    ISIC_ELASTICSEARCH_INDEX = 'isic'

    CELERY_WORKER_MAX_MEMORY_PER_CHILD = 256 * 1024


class DevelopmentConfiguration(IsicMixin, DevelopmentBaseConfiguration):
    # Development-only settings
    SHELL_PLUS_IMPORTS = [
        'from isic.ingest.tasks import *',
        'from isic.studies.tasks import *',
        'from django.core.files.uploadedfile import UploadedFile',
        'import pandas as pd',
        'from isic.ingest.validators import *',
        'from opensearchpy import OpenSearch',
        'from isic.core.search import *',
    ]
    ISIC_MONGO_URI = values.Value(None)
    # Allow developers to run tasks synchronously for easy debugging
    CELERY_TASK_ALWAYS_EAGER = values.BooleanValue(False)
    CELERY_TASK_EAGER_PROPAGATES = values.BooleanValue(False)


class TestingConfiguration(IsicMixin, TestingBaseConfiguration):
    ISIC_DISCOURSE_SSO_SECRET = 'discourse_secret'
    ISIC_MONGO_URI = None
    ISIC_ELASTICSEARCH_INDEX = 'isic-testing'


class ProductionConfiguration(IsicMixin, ProductionBaseConfiguration):
    pass


class HerokuProductionConfiguration(IsicMixin, HerokuProductionBaseConfiguration):
    ISIC_ELASTICSEARCH_URI = values.SecretValue(environ_name='SEARCHBOX_URL', environ_prefix=None)
