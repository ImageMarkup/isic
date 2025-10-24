# Generated manually for similar image feedback feature

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0035_image_image_embedding_ivfflat_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SimilarImageFeedback",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "feedback",
                    models.CharField(
                        choices=[("up", "Thumbs Up"), ("down", "Thumbs Down")], max_length=10
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        help_text="The source image being viewed",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="similarity_feedback_source",
                        to="core.image",
                    ),
                ),
                (
                    "similar_image",
                    models.ForeignKey(
                        help_text="The similar image being rated",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="similarity_feedback_target",
                        to="core.image",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "verbose_name": "Similar Image Feedback",
                "verbose_name_plural": "Similar Image Feedback",
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="similarimagefeedback",
            constraint=models.UniqueConstraint(
                fields=("image", "similar_image", "user"), name="similar_image_feedback_unique"
            ),
        ),
    ]
