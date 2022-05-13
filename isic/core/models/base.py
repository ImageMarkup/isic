from fnmatch import fnmatch

from django.conf import settings
from django.db import models
from django_extensions.db.fields import CreationDateTimeField
from django_extensions.db.models import TimeStampedModel
from oauth2_provider.models import AbstractApplication


class CreationSortedTimeStampedModel(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        abstract = True
        ordering = ['-created']
        get_latest_by = 'created'

    created = CreationDateTimeField(db_index=True)


class CopyrightLicense(models.TextChoices):
    CC_0 = 'CC-0', 'CC-0'

    # These 2 require attribution
    CC_BY = 'CC-BY', 'CC-BY'
    CC_BY_NC = 'CC-BY-NC', 'CC-BY-NC'


class IsicOAuthApplication(AbstractApplication):
    def redirect_uri_allowed(self, uri):
        if settings.ISIC_OAUTH_ALLOW_WILDCARD_REDIRECT_URIS:
            return any(fnmatch(uri, redirect_uri) for redirect_uri in self.redirect_uris.split())
        else:
            return super().redirect_uri_allowed(uri)
