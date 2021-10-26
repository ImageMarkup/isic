# Generated by Django 3.2.8 on 2021-10-29 16:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0048_accession_cohort'),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE ingest_accession set cohort_id = ingest_zip.cohort_id
            FROM ingest_zip, ingest_cohort
            WHERE ingest_accession.upload_id = ingest_zip.id
            AND ingest_zip.cohort_id = ingest_cohort.id;
            """
        ),
    ]