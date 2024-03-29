# Generated by Django 4.0.3 on 2022-04-16 19:24
from __future__ import annotations

import contextlib

from django.db import migrations
from django.db.models.aggregates import Max
from django.db.models.query_utils import Q


def migrate_checks(apps, schema_editor):
    Accession = apps.get_model("ingest", "Accession")
    CheckLog = apps.get_model("ingest", "CheckLog")

    failed_review_filter = (
        Q(lesion_check=False)
        | Q(quality_check=False)
        | Q(phi_check=False)
        | Q(duplicate_check=False)
        | Q(diagnosis_check=False)
    )
    unpublished_rejected_accessions = Accession.objects.filter(image=None).filter(
        failed_review_filter
    )
    unpublished_other_accessions = Accession.objects.filter(image=None).exclude(
        failed_review_filter
    )

    for accession in unpublished_rejected_accessions.iterator():
        with contextlib.suppress(CheckLog.DoesNotExist):
            first_failed_checklog = accession.checklogs.filter(change_to=False).earliest()

        accession.checklogs.exclude(pk=first_failed_checklog.pk).delete()

    CheckLog.objects.filter(accession__in=unpublished_other_accessions).delete()

    published_accessions = Accession.objects.exclude(image=None)
    keep_checklogs = set(
        published_accessions.annotate(last_passed_checklog=Max("checklogs__id"))
        .exclude(last_passed_checklog=None)
        .values_list("last_passed_checklog", flat=True)
    )
    checklog_delete = set()
    for checklog in CheckLog.objects.filter(accession__in=published_accessions).iterator():
        if checklog.id not in keep_checklogs:
            checklog_delete.add(checklog.id)
    CheckLog.objects.filter(id__in=checklog_delete).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0007_auto_20220413_1820"),
    ]

    operations = [
        migrations.RunPython(migrate_checks),
    ]
