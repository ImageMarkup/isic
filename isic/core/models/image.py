from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.core.dsl import parse_query
from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId

RESTRICTED_METADATA_FIELDS = ['age', 'patient_id', 'lesion_id']


class ImageQuerySet(models.QuerySet):
    def from_search_query(self, query: str):
        if query == '':
            return self
        else:
            return self.filter(parse_query(query))


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

    # index is used because public is filtered in every permissions check
    public = models.BooleanField(default=False, db_index=True)

    shares = models.ManyToManyField(
        User, through='ImageShare', through_fields=['image', 'recipient']
    )

    objects = ImageQuerySet.as_manager()

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse('core/image-detail', args=[self.pk])

    @property
    def as_elasticsearch_document(self) -> dict:
        document = {
            'id': self.pk,
            'created': self.created,
            'isic_id': self.isic_id,
            'public': self.public,
            # TODO: make sure these fields can't be searched on
            'contributor_owner_ids': [
                user.pk for user in self.accession.cohort.contributor.owners.all()
            ],
            'shared_to': [user.pk for user in self.shares.all()],
            'collections': list(self.collections.values_list('pk', flat=True)),
        }

        # Fields in the search index have to be redacted otherwise the documents that match could
        # leak what their true metadata values are.
        document.update(self.accession.redacted_metadata)

        return document


class ImageShare(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='shares')
    image = models.ForeignKey(Image, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)


class ImagePermissions:
    model = Image
    perms = ['view_image', 'view_full_metadata']
    filters = {'view_image': 'view_image_list', 'view_full_metadata': 'view_full_metadata_list'}

    @staticmethod
    def view_full_metadata_list(
        user_obj: User, qs: Optional[QuerySet[Image]] = None
    ) -> QuerySet[Image]:
        # Allows viewing unstructured metadata as well as the redacted metadata fields.
        #
        # This is only used in an SSR context, the API doesn't yet reveal more.
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif not user_obj.is_anonymous:
            return qs.filter(accession__cohort__contributor__owners=user_obj)
        else:
            return qs.none()

    @staticmethod
    def view_full_metadata(user_obj: User, obj: Image) -> bool:
        # TODO: use .contains in django 4
        return ImagePermissions.view_full_metadata_list(user_obj).filter(pk=obj.pk).exists()

    @staticmethod
    def view_image_list(user_obj: User, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_active and user_obj.is_staff:
            return qs
        elif user_obj.is_active and not user_obj.is_anonymous:
            # Note: permissions here must be also modified in build_elasticsearch_query
            return qs.filter(
                Q(public=True)
                | Q(accession__cohort__contributor__owners=user_obj)
                | Q(shares=user_obj)
            )
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_image(user_obj: User, obj: Image) -> bool:
        # TODO: use .contains in django 4
        return ImagePermissions.view_image_list(user_obj).filter(pk=obj.pk).exists()


Image.perms_class = ImagePermissions
