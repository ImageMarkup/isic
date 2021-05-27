from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Q, UniqueConstraint
from django.urls import reverse
from django.utils.safestring import mark_safe

from isic.core.models import CopyrightLicense, CreationSortedTimeStampedModel

from .contributor import Contributor


class Cohort(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        constraints = [
            UniqueConstraint(
                name='cohort_unique_girder_id', fields=['girder_id'], condition=~Q(girder_id='')
            )
        ]

    contributor = models.ForeignKey(Contributor, on_delete=models.PROTECT, related_name='cohorts')
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text='The dataset_id from Girder.')

    name = models.CharField(
        max_length=255,
        help_text=mark_safe(
            'The name of your Cohort. '
            '<strong>This is private</strong>, and will '
            'not be published along with your images.'
        ),
    )
    description = models.TextField(
        help_text=mark_safe(
            'The description of your Cohort.'
            '<strong>This is private</strong>, and will not be published along '
            'with your images.'
        )
    )

    copyright_license = models.CharField(choices=CopyrightLicense.choices, max_length=255)

    # required if copyright_license is CC-BY-*
    attribution = models.TextField()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse('cohort-detail', args=[self.id])

    def unreviewed(self):
        from .accession import Accession
        from .distinctness_measure import DistinctnessMeasure

        duplicate_cohort_checksums = (
            DistinctnessMeasure.objects.values('checksum')
            .annotate(is_duplicate=Count('checksum'))
            .filter(is_duplicate__gt=1, accession__upload__cohort=self)
            .values_list('checksum')
        )

        return Accession.objects.filter(upload__cohort=self).filter(
            Q(quality_check=None)
            | Q(diagnosis_check=None)
            | Q(phi_check=None)
            | (Q(lesion_check=None) & Q(metadata__lesion_id__isnull=False))
            | (
                Q(duplicate_check=None)
                & Q(distinctnessmeasure__checksum__in=duplicate_cohort_checksums)
            ),
        )
