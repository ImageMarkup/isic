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


class IsicConfig(ConfigMixin):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

    @staticmethod
    def before_binding(configuration: ComposedConfiguration) -> None:
        configuration.INSTALLED_APPS += [
            'isic.studies.apps.StudiesConfig',
            's3_file_field',
            'oauth2_provider',
            'material',
        ]

        # Insert before the allauth app, to ensure our base.html is found first
        allauth_index = configuration.INSTALLED_APPS.index('allauth')
        configuration.INSTALLED_APPS.insert(allauth_index, 'isic.login.apps.LoginConfig')

        if configuration.ISIC_DISCOURSE_SSO_SECRET:
            configuration.INSTALLED_APPS += [
                'isic.discourse_sso.apps.DiscourseSSOConfig',
            ]

        # PASSWORD_HASHERS are ordered "best" to "worst", appending Girder last means
        # it will be upgraded on login.
        configuration.PASSWORD_HASHERS += ['isic.login.backends.GirderPasswordHasher']

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

    AUTHENTICATION_BACKENDS = [
        'isic.login.backends.GirderBackend',
        'allauth.account.auth_backends.AuthenticationBackend',
    ]

    ISIC_DISCOURSE_SSO_SECRET = values.Value(
        None,
        # Don't bind late, so the value can be examined in before_binding
        late_binding=False,
        # Without late_binding, environ_name must be explicitly set for the setting to know its
        # own name early enough
        environ_name='ISIC_DISCOURSE_SSO_SECRET',
    )
    ISIC_MONGO_URI = values.SecretValue()


class DevelopmentConfiguration(IsicConfig, DevelopmentBaseConfiguration):
    AUTHENTICATION_BACKENDS = [
        'allauth.account.auth_backends.AuthenticationBackend',
    ]
    ALLOWED_REDIRECT_URI_SCHEMES = ['http', 'https']

    ISIC_MONGO_URI = values.Value('mongodb://localhost:27017/girder')


class TestingConfiguration(IsicConfig, TestingBaseConfiguration):
    ISIC_DISCOURSE_SSO_SECRET = 'discourse_secret'
    ISIC_MONGO_URI = 'mongodb://localhost:27017/girder'


class ProductionConfiguration(IsicConfig, ProductionBaseConfiguration):
    pass


class HerokuProductionConfiguration(IsicConfig, HerokuProductionBaseConfiguration):
    pass
