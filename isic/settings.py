from __future__ import annotations

from pathlib import Path

from configurations import values
from django_girders.configuration import (
    ComposedConfiguration,
    ConfigMixin,
    DevelopmentBaseConfiguration,
    HerokuProductionBaseConfiguration,
    ProductionBaseConfiguration,
)


class IsicConfig(ConfigMixin):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = str(Path(__file__).absolute().parent.parent)

    DISCOURSE_SSO_SECRET = values.SecretValue()
    ARCHIVE_MONGO_URI = values.SecretValue()

    @staticmethod
    def before_binding(configuration: ComposedConfiguration) -> None:
        configuration.INSTALLED_APPS += [
            'isic.login.apps.LoginConfig',
            'isic.discourse_sso.apps.DiscourseSSOConfig',
            'oauth2_provider',
        ]
        configuration.REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.BasicAuthentication',
                'rest_framework.authentication.TokenAuthentication',
                'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
        }
        configuration.OAUTH2_PROVIDER = {
            'SCOPES': {
                'identity': 'Access to your basic profile information',
                'image:read': 'Read access to images',
                'image:write': 'Write access to images',
            },
            'DEFAULT_SCOPES': ['identity'],
            'ACCESS_TOKEN_MODEL': 'isic.login.apps.LoginConfig.GirderOAuthAccessToken',
        }
        configuration.PKCE_REQUIRED = True

        configuration.AUTHENTICATION_BACKENDS = [
            'isic.login.girder.GirderBackend',
            'django.contrib.auth.backends.ModelBackend',
        ]


class DevelopmentConfiguration(IsicConfig, DevelopmentBaseConfiguration):
    DISCOURSE_SSO_SECRET = values.Value()
    ARCHIVE_MONGO_URI = values.Value('mongodb://localhost:27017/girder')


class ProductionConfiguration(IsicConfig, ProductionBaseConfiguration):
    ALLOWED_REDIRECT_URI_SCHEMES = ['https']


class HerokuProductionConfiguration(IsicConfig, HerokuProductionBaseConfiguration):
    pass
