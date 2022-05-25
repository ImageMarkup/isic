import re

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
    class Meta:
        verbose_name = 'ISIC OAuth application'

    def redirect_uri_allowed(self, uri):
        if settings.ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS:
            for redirect_uri in self.redirect_uris.split():
                if redirect_uri.startswith('^') and re.match(redirect_uri, uri):
                    return True

        return super().redirect_uri_allowed(uri)
