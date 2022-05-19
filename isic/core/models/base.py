import re

from django.conf import settings
from django.db import models
from django_extensions.db.fields import CreationDateTimeField
from django_extensions.db.models import TimeStampedModel
from oauth2_provider.models import AbstractApplication, redirect_to_uri_allowed


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
        regex_redirect_uris = [
            redirect_uri
            for redirect_uri in self.redirect_uris.split()
            if redirect_uri.startswith('^')
        ]
        non_regex_redirect_uris = [
            redirect_uri
            for redirect_uri in self.redirect_uris.split()
            if not redirect_uri.startswith('^')
        ]

        if settings.ISIC_OAUTH_ALLOW_REGEX_REDIRECT_URIS:
            matches_regex_uri = any(
                re.match(redirect_uri_regex, uri) for redirect_uri_regex in regex_redirect_uris
            )

            if matches_regex_uri:
                return True

        return redirect_to_uri_allowed(uri, non_regex_redirect_uris)
