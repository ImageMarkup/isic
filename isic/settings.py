from __future__ import annotations

import os
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


class IsicConfig(ConfigMixin):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

    @staticmethod
    def before_binding(configuration: ComposedConfiguration) -> None:
        configuration.INSTALLED_APPS += [
            'isic.login',
            'oauth2_provider',
            'material',
        ]

        if configuration.ISIC_DISCOURSE_SSO_SECRET:
            print('loading discourse sso')
            configuration.INSTALLED_APPS += [
                'isic.discourse_sso.apps.DiscourseSSOConfig',
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

    # late binding = false so we can optionally check in before_binding
    ISIC_DISCOURSE_SSO_SECRET = values.Value(None, late_binding=False)
    ISIC_MONGO_URI = values.SecretValue()


class DevelopmentConfiguration(IsicConfig, DevelopmentBaseConfiguration):
    AUTHENTICATION_BACKENDS = [
        'isic.login.girder.GirderBackend',
        'django.contrib.auth.backends.ModelBackend',
    ]
    ALLOWED_REDIRECT_URI_SCHEMES = ['http', 'https']

    # ISIC_DISCOURSE_SSO_SECRET = values.Value('discourse_secret', late_binding=False)
    ISIC_MONGO_URI = values.Value('mongodb://localhost:27017/girder')


class TestingConfiguration(IsicConfig, TestingBaseConfiguration):
    ISIC_DISCOURSE_SSO_SECRET = 'discourse_secret'
    ISIC_MONGO_URI = 'mongodb://localhost:27017/girder'


class ProductionConfiguration(IsicConfig, ProductionBaseConfiguration):
    pass


class HerokuProductionConfiguration(IsicConfig, HerokuProductionBaseConfiguration):
    pass
