from __future__ import annotations

from pathlib import Path

from configurations import values
from django_girders.configuration import (
    ComposedConfiguration,
    ConfigMixin,
    DevelopmentBaseConfiguration,
    HerokuProductionBaseConfiguration,
    ProductionBaseConfiguration,
    TestingBaseConfiguration,
)


class IsicConfig(ConfigMixin):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = str(Path(__file__).absolute().parent.parent)

    @staticmethod
    def before_binding(configuration: ComposedConfiguration) -> None:
        configuration.INSTALLED_APPS += [
            'isic.login',
            'isic.discourse_sso.apps.DiscourseSSOConfig',
            'oauth2_provider',
            'material',
        ]

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.BasicAuthentication',
            'rest_framework.authentication.TokenAuthentication',
            'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    }
    OAUTH2_PROVIDER = {
        'SCOPES': {
            'identity': 'Access to your basic profile information',
            'image:read': 'Read access to images',
            'image:write': 'Write access to images',
        },
        'DEFAULT_SCOPES': ['identity'],
    }
    PKCE_REQUIRED = True
    ALLOWED_REDIRECT_URI_SCHEMES = ['https']

    AUTHENTICATION_BACKENDS = ['isic.login.girder.GirderBackend']
    LOGIN_URL = '/accounts/login'

    ISIC_DISCOURSE_SSO_SECRET = values.SecretValue()
    ISIC_MONGO_URI = values.SecretValue()


class DevelopmentConfiguration(IsicConfig, DevelopmentBaseConfiguration):
    AUTHENTICATION_BACKENDS = [
        'isic.login.girder.GirderBackend',
        'django.contrib.auth.backends.ModelBackend',
    ]
    ALLOWED_REDIRECT_URI_SCHEMES = ['http', 'https']

    ISIC_DISCOURSE_SSO_SECRET = values.Value('discourse_secret')
    ISIC_MONGO_URI = values.Value('mongodb://localhost:27017/girder')


class TestingConfiguration(IsicConfig, TestingBaseConfiguration):
    ISIC_DISCOURSE_SSO_SECRET = 'discourse_secret'
    ISIC_MONGO_URI = 'mongodb://localhost:27017/girder'


class ProductionConfiguration(IsicConfig, ProductionBaseConfiguration):
    pass


class HerokuProductionConfiguration(IsicConfig, HerokuProductionBaseConfiguration):
    pass
