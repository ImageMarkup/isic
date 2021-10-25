from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId

RESTRICTED_SEARCH_FIELDS = ['age', 'patient_id', 'lesion_id']


class Image(CreationSortedTimeStampedModel):
    accession = models.OneToOneField(
        Accession,
        on_delete=models.PROTECT,
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(
        IsicId,
        on_delete=models.PROTECT,
        default=IsicId.safe_create,
        editable=False,
        verbose_name='isic id',
    )

    public = models.BooleanField(default=False)

    shares = models.ManyToManyField(
        User, through='ImageShare', through_fields=['image', 'recipient']
    )

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse('core/image-detail', args=[self.pk])

    @property
    def as_elasticsearch_document(self) -> dict:
        # This dict's values should all be immutable, otherwise a deep copy would be necessary
        document = dict(self.accession.metadata)

        # The age has to be stored in the search index in rounded form, otherwise searches
        # (e.g. 'age:47') could leak the true age.
        if 'age' in document:
            document['age_approx'] = self.accession.age_approx

        for f in RESTRICTED_SEARCH_FIELDS:
            if f in document:
                del document[f]

        document.update(
            {
                'id': self.pk,
                'created': self.created,
                'isic_id': self.isic_id,
                'public': self.public,
                # TODO: make sure these fields can't be searched on
                'contributor_owner_ids': [
                    user.pk for user in self.accession.upload.cohort.contributor.owners.all()
                ],
                'shared_to': [user.pk for user in self.shares.all()],
                'collections': list(self.collections.values_list('pk', flat=True)),
            }
        )

        return document


class ImageShare(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='shares')
    image = models.ForeignKey(Image, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)


class ImagePermissions:
    model = Image
    perms = ['view_image']
    filters = {'view_image': 'view_image_list'}

    @staticmethod
    def view_image_list(user_obj: User, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_active and user_obj.is_staff:
            return qs
        elif user_obj.is_active and not user_obj.is_anonymous:
            return qs.filter(
                Q(public=True)
                | Q(accession__upload__cohort__contributor__owners=user_obj)
                | Q(shares=user_obj)
            )
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_image(user_obj: User, obj: Image) -> bool:
        # TODO: use .contains in django 4
        return ImagePermissions.view_image_list(user_obj).filter(pk=obj.pk).exists()


Image.perms_class = ImagePermissions
