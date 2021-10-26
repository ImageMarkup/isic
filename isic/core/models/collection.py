from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.ingest.models.cohort import Cohort

from .doi import Doi
from .image import Image


class Collection(TimeStampedModel):
    images = models.ManyToManyField(Image, related_name='collections')

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    public = models.BooleanField(default=False)

    doi = models.OneToOneField(Doi, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('core/collection-detail', args=[self.pk])

    def _get_datacite_creators(self) -> list[str]:
        """
        Return a list of datacite creators for this collection.

        Creators are ordered by number of images contributed (to this collection), ties are broken
        alphabetically, except for Anonymous contributions which are always last.
        """
        creator_cohorts = (
            Cohort.objects.alias(
                num_images=Count(
                    'zips__accessions__image', filter=Q(zips__accessions__image__collections=self)
                )
            )
            .filter(pk__in=self.images.values('accession__upload__cohort').distinct())
            .order_by('-num_images', 'attribution')
            .distinct()
        )

        creators = creator_cohorts.values_list('attribution', flat=True)

        # Push Anonymous attributions to last
        creators = sorted(creators, key=lambda x: 1 if x == 'Anonymous' else 0)

        return creators

    def as_datacite_doi(self, contributor: User, doi_id: str) -> dict:
        return {
            'data': {
                'type': 'dois',
                'attributes': {
                    'identifiers': [{'identifierType': 'DOI', 'identifier': doi_id}],
                    'event': 'publish',
                    'doi': doi_id,
                    'creators': [{'name': creator} for creator in self._get_datacite_creators()],
                    'contributor': f'{contributor.first_name} {contributor.last_name}',
                    'titles': [{'title': self.name}],
                    'publisher': 'ISIC Archive',
                    'publicationYear': self.images.order_by('created').latest().created.year,
                    # resourceType?
                    'types': {'resourceTypeGeneral': 'Dataset'},
                    # TODO: api.?
                    'url': f'https://api.isic-archive.com/collections/{self.pk}',
                    'schemaVersion': 'http://datacite.org/schema/kernel-4',
                    'description': self.description,
                    'descriptionType': 'Other',
                },
            }
        }


class CollectionPermissions:
    model = Collection
    perms = ['view_collection', 'create_doi']
    filters = {'view_collection': 'view_collection_list', 'create_doi': 'create_doi_list'}

    @staticmethod
    def view_collection_list(
        user_obj: User, qs: Optional[QuerySet[Collection]] = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_active and user_obj.is_staff:
            return qs
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_collection(user_obj, obj):
        # TODO: use .contains in django 4
        return CollectionPermissions.view_collection_list(user_obj).filter(pk=obj.pk).exists()

    @staticmethod
    def create_doi_list(
        user_obj: User, qs: Optional[QuerySet[Collection]] = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        # TODO: allow collection creators to create a DOI (when collection creators exist)
        if user_obj.is_active and user_obj.is_staff:
            return qs
        else:
            return qs.none()

    @staticmethod
    def create_doi(user_obj: User, obj: Collection) -> bool:
        return CollectionPermissions.create_doi_list(user_obj).filter(pk=obj.pk).exists()


Collection.perms_class = CollectionPermissions
