from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .doi import Doi
from .image import Image


class Collection(TimeStampedModel):
    """
    Collections are unordered groups of images.

    Collections are locked and then nothing can be modified except for
    adding a DOI. Once locked, no images can be added either.

    A collection can be public or private. Public collections cannot contain
    private images.
    """

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    images = models.ManyToManyField(Image, related_name='collections')

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    public = models.BooleanField(default=False)

    official = models.BooleanField(default=False)

    doi = models.OneToOneField(Doi, on_delete=models.PROTECT, null=True, blank=True)

    locked = models.BooleanField(default=False)

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
        creators = (
            self.images.alias(num_images=Count('accession__image'))
            .values_list('accession__cohort__attribution', flat=True)
            .order_by('-num_images', 'accession__cohort__attribution')
            .distinct()
        )

        # Push an Anonymous attribution to the end
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
                    'contributor': f'{self.creator.first_name} {self.creator.last_name}',
                    'titles': [{'title': self.name}],
                    'publisher': 'ISIC Archive',
                    'publicationYear': self.images.order_by('created').latest().created.year,
                    # resourceType?
                    'types': {'resourceTypeGeneral': 'Dataset'},
                    # TODO: api.?
                    'url': f'https://api.isic-archive.com/collections/{self.pk}/',
                    'schemaVersion': 'http://datacite.org/schema/kernel-4',
                    'description': self.description,
                    'descriptionType': 'Other',
                },
            }
        }

    @property
    def doi_url(self):
        if self.doi:
            return f'https://doi.org/{self.doi}'

    def save(self, **kwargs):
        # Check for updates to the collection
        # TODO: allow creating a DOI for locked collections
        if self.pk and Collection.objects.filter(pk=self.pk, locked=True).exists():
            raise ValidationError("Can't modify the collection, it's locked.")

        return super().save(**kwargs)


@receiver(m2m_changed, sender=Collection.images.through)
def collection_images_change(sender, instance: Collection, action: str, **kwargs) -> None:
    if action == 'pre_add':
        if isinstance(instance, Collection):
            if instance.locked:
                raise ValidationError('Attempting to add images to a locked collection.')

            if (
                instance.public
                and kwargs['model'].objects.filter(public=False, pk__in=kwargs['pk_set']).exists()
            ):
                raise ValidationError('Attempting to add private images to a public collection.')
        elif isinstance(instance, Image):
            locked_colls = (
                kwargs['model'].objects.filter(locked=True, pk__in=kwargs['pk_set']).exists()
            )
            if locked_colls:
                raise ValidationError('Attempting to add locked collections to an image.')

            public_colls = (
                kwargs['model'].objects.filter(public=True, pk__in=kwargs['pk_set']).exists()
            )
            if not instance.public and public_colls:
                raise ValidationError('Attempting to add public collections to a private image.')


class CollectionPermissions:
    model = Collection
    perms = ['view_collection', 'create_doi', 'add_images']
    filters = {'view_collection': 'view_collection_list', 'create_doi': 'create_doi_list'}

    @staticmethod
    def view_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(Q(public=True) | Q(creator=user_obj))
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_collection(user_obj, obj):
        # TODO: use .contains in django 4
        return CollectionPermissions.view_collection_list(user_obj).filter(pk=obj.pk).exists()

    @staticmethod
    def create_doi_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        else:
            return qs.none()

    @staticmethod
    def create_doi(user_obj: User, obj: Collection) -> bool:
        return CollectionPermissions.create_doi_list(user_obj).filter(pk=obj.pk).exists()

    @staticmethod
    def add_images_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(creator=user_obj)
        else:
            return qs.none()

    @staticmethod
    def add_images(user_obj, obj: Collection):
        # TODO: use .contains in django 4
        return CollectionPermissions.add_images_list(user_obj).filter(pk=obj.pk).exists()


Collection.perms_class = CollectionPermissions
