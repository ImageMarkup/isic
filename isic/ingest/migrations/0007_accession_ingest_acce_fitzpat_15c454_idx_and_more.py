# Generated by Django 5.1.1 on 2024-10-05 00:51

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0006_accession_valid_diagnosis_accession_valid_legacy_dx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                fields=["fitzpatrick_skin_type"], name="ingest_acce_fitzpat_15c454_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                condition=models.Q(
                    (
                        "anatom_site_general__in",
                        ["palms/soles", "lateral torso", "oral/genital"],
                    )
                ),
                fields=["anatom_site_general"],
                name="accession_anatom_site_general",
            ),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                condition=models.Q(("benign_malignant", "benign"), _negated=True),
                fields=["benign_malignant"],
                name="accession_benign_malignant",
            ),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                condition=models.Q(("diagnosis__in", [None, "", "Benign"]), _negated=True),
                fields=["diagnosis"],
                name="accession_diagnosis",
            ),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["legacy_dx"], name="ingest_acce_legacy__33310d_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["mel_class"], name="ingest_acce_mel_cla_716507_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["mel_mitotic_index"], name="ingest_acce_mel_mit_261415_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["mel_type"], name="ingest_acce_mel_typ_5d54e1_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["mel_ulcer"], name="ingest_acce_mel_ulc_d11b54_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(fields=["nevus_type"], name="ingest_acce_nevus_t_8c8b30_idx"),
        ),
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                condition=models.Q(
                    ("image_type__in", ["TBP tile: close-up", "dermoscopic"]),
                    _negated=True,
                ),
                fields=["image_type"],
                name="accession_image_type",
            ),
        ),
    ]
