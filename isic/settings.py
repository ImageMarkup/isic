from __future__ import annotations

from pathlib import Path

from configurations import values
from django_girders.configuration import DevelopmentBaseConfiguration


class DevelopmentConfiguration(DevelopmentBaseConfiguration):
    WSGI_APPLICATION = 'isic.wsgi.application'
    ROOT_URLCONF = 'isic.urls'

    BASE_DIR = str(Path(__file__).absolute().parent.parent)

    DISCOURSE_SSO_SECRET = values.SecretValue()
    ARCHIVE_MONGO_URI = values.SecretValue()

    @staticmethod
    def before_binding(configuration: DevelopmentConfiguration) -> None:
        configuration.INSTALLED_APPS += ['isic.discourse_sso']
