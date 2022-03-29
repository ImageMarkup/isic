import re

from deepdiff import DeepDiff
from django.contrib.auth.models import User
from django.db import models

from isic.core.models import CreationSortedTimeStampedModel

from .accession import Accession


class MetadataRevisionQuerySet(models.QuerySet):
    def differences(self) -> list:
        revisions = list(self.order_by('created'))
        diffs = []

        # prepend revisions with an empty revision so an initial diff is generated
        for prev, cur in zip(
            [MetadataRevision(metadata={}, unstructured_metadata={})] + revisions, revisions
        ):
            diffs.append((cur, prev.diff(cur)))

        return diffs


class MetadataRevision(CreationSortedTimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='metadata_revisions')
    accession = models.ForeignKey(
        Accession, on_delete=models.PROTECT, related_name='metadata_revisions'
    )
    metadata = models.JSONField()
    unstructured_metadata = models.JSONField()

    objects = MetadataRevisionQuerySet.as_manager()

    def diff(self, other: 'MetadataRevision'):
        def _strip_root(key: str) -> str:
            return re.sub(r"^root\['(.*)'\]$", r'\1', key)

        def _diff(a, b):
            result = DeepDiff(
                a,
                b,
                ignore_order=True,
                verbose_level=2,
            )
            formatted_result = {
                'added': {},
                'removed': {},
                'changed': {},
            }
            for key, value in result.get('dictionary_item_added', {}).items():
                formatted_result['added'][_strip_root(key)] = value
            for key, value in result.get('dictionary_item_removed', {}).items():
                formatted_result['removed'][_strip_root(key)] = value
            for key, value in result.get('values_changed', {}).items():
                formatted_result['changed'][_strip_root(key)] = value

            return formatted_result

        return {
            'metadata': _diff(self.metadata, other.metadata),
            'unstructured_metadata': _diff(self.unstructured_metadata, other.unstructured_metadata),
        }
