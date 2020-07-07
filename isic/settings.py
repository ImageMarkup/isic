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
        configuration.INSTALLED_APPS += ['isic.discourse_sso.apps.DiscourseSSOConfig']


class DevelopmentConfiguration(IsicConfig, DevelopmentBaseConfiguration):
    DISCOURSE_SSO_SECRET = 'secret'
    ARCHIVE_MONGO_URI = values.Value('mongodb://localhost:27017/girder')


class ProductionConfiguration(IsicConfig, ProductionBaseConfiguration):
    pass


class HerokuProductionConfiguration(IsicConfig, HerokuProductionBaseConfiguration):
    pass
