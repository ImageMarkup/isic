from __future__ import annotations

import re

from django.contrib.auth.models import User
from django.db import models

from isic.ingest.utils.json import DecimalAwareJSONEncoder

from .accession import Accession


class MetadataVersionQuerySet(models.QuerySet):
    def differences(self) -> list:
        versions = list(self.order_by("created"))
        diffs = []

        # prepend versions with an empty version so an initial diff is generated
        for prev, cur in zip(
            [MetadataVersion(metadata={}, unstructured_metadata={}), *versions],
            versions,
            strict=False,
        ):
            diffs.append((cur, prev.diff(cur)))

        return diffs


class MetadataVersion(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="metadata_versions")
    accession = models.ForeignKey(
        Accession, on_delete=models.PROTECT, related_name="metadata_versions"
    )
    # since metadata fields can be Decimal values, this field needs to use a custom encoder.
    metadata = models.JSONField(encoder=DecimalAwareJSONEncoder)
    unstructured_metadata = models.JSONField()
    lesion = models.JSONField(default=dict)
    patient = models.JSONField(default=dict)
    rcm_case = models.JSONField(default=dict)

    objects = MetadataVersionQuerySet.as_manager()

    class Meta:
        ordering = ["-created"]
        get_latest_by = "created"

    def __str__(self) -> str:
        return str(self.id)

    def diff(self, other: MetadataVersion):
        def _strip_root(key: str) -> str:
            return re.sub(r"^root\['(.*)'\]$", r"\1", key)

        def _diff(a, b):
            from deepdiff import DeepDiff

            result = DeepDiff(
                a,
                b,
                ignore_order=True,
                verbose_level=2,
            )
            formatted_result = {
                "added": {},
                "removed": {},
                "changed": {},
            }
            for key, value in result.get("dictionary_item_added", {}).items():
                formatted_result["added"][_strip_root(key)] = value
            for key, value in result.get("dictionary_item_removed", {}).items():
                formatted_result["removed"][_strip_root(key)] = value
            for key, value in result.get("values_changed", {}).items():
                formatted_result["changed"][_strip_root(key)] = value

            return formatted_result

        return {
            "metadata": _diff(self.metadata, other.metadata),
            "unstructured_metadata": _diff(self.unstructured_metadata, other.unstructured_metadata),
            "lesion": _diff(self.lesion, other.lesion),
            "patient": _diff(self.patient, other.patient),
            "rcm_case": _diff(self.rcm_case, other.rcm_case),
        }
