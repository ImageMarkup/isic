from django.db import models


class CollectionCount(models.Model):
    id = models.OneToOneField(
        "core.Collection",
        on_delete=models.DO_NOTHING,  # rows can't be deleted from a materialized view
        related_name="cached_counts",
        primary_key=True,
        db_column="id",
    )
    lesion_count = models.PositiveIntegerField()
    patient_count = models.PositiveIntegerField()
    image_count = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = "materialized_collection_counts"

    def __str__(self):
        return f"CollectionCount collection_id={self.pk}, lesion_count={self.lesion_count}, patient_count={self.patient_count}, image_count={self.image_count}"  # noqa: E501
