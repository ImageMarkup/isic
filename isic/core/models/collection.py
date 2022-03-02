from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.aggregates import Count
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
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

    class Meta(TimeStampedModel.Meta):
        unique_together = [['creator', 'name']]
        constraints = [
            UniqueConstraint(
                name='collection_official_has_unique_name',
                fields=['name'],
                condition=Q(official=True),
            )
        ]

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    images = models.ManyToManyField(Image, related_name='collections')

    # unique per user. names of official collections can't be used.
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    public = models.BooleanField(default=False)

    shares = models.ManyToManyField(
        User,
        through='CollectionShare',
        through_fields=['collection', 'recipient'],
        related_name='collection_shares',
    )

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

        if self.pk and self.public and self.images.filter(public=False).exists():
            raise ValidationError("Can't make collection public, it contains private images.")

        return super().save(**kwargs)


@receiver(
    m2m_changed,
    sender=Collection.images.through,
    dispatch_uid='block_private_images_in_public_collections',
)
def block_private_images_in_public_collections(
    sender, instance: Collection, action: str, **kwargs
) -> None:
    if action == 'pre_add':
        if isinstance(instance, Collection):
            if (
                instance.public
                and kwargs['model'].objects.filter(public=False, pk__in=kwargs['pk_set']).exists()
            ):
                raise ValidationError('Attempting to add private images to a public collection.')
        elif isinstance(instance, Image):
            public_colls = (
                kwargs['model'].objects.filter(public=True, pk__in=kwargs['pk_set']).exists()
            )
            if not instance.public and public_colls:
                raise ValidationError('Attempting to add public collections to a private image.')


@receiver(
    m2m_changed, sender=Collection.images.through, dispatch_uid='block_locked_collection_mutation'
)
def block_locked_collection_mutation(sender, instance: Collection, action: str, **kwargs) -> None:
    if action == 'pre_clear':
        if isinstance(instance, Collection):
            if instance.locked and instance.images.exists():
                raise ValidationError('Attempting to clear images from a locked collection.')
        elif isinstance(instance, Image):
            locked_colls = instance.collections.filter(locked=True).exists()
            if locked_colls:
                raise ValidationError('Attempting to remove a locked collection from an image.')

    if action == 'pre_remove':
        if isinstance(instance, Collection):
            if instance.locked:
                raise ValidationError('Attempting to remove images from a locked collection.')
        elif isinstance(instance, Image):
            locked_colls = (
                kwargs['model'].objects.filter(locked=True, pk__in=kwargs['pk_set']).exists()
            )
            if locked_colls:
                raise ValidationError('Attempting to remove a locked collection from an image.')

    if action == 'pre_add':
        if isinstance(instance, Collection):
            if instance.locked:
                raise ValidationError('Attempting to add images to a locked collection.')
        elif isinstance(instance, Image):
            locked_colls = (
                kwargs['model'].objects.filter(locked=True, pk__in=kwargs['pk_set']).exists()
            )
            if locked_colls:
                raise ValidationError('Attempting to add locked collections to an image.')


class CollectionShare(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name='collectionshare_creator_recipient_diff_check',
                check=~Q(creator=F('recipient')),
            )
        ]

    creator = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='collection_shares_given'
    )
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='collection_shares_received'
    )


class CollectionPermissions:
    model = Collection
    perms = ['view_collection', 'edit_collection', 'create_doi', 'add_images']
    filters = {'view_collection': 'view_collection_list', 'create_doi': 'create_doi_list'}

    @staticmethod
    def _is_creator_list(
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
    def view_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(Q(public=True) | Q(creator=user_obj) | Q(shares=user_obj))
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_collection(user_obj, obj):
        return CollectionPermissions.view_collection_list(user_obj).contains(obj)

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
        return CollectionPermissions.create_doi_list(user_obj).contains(obj)

    @staticmethod
    def add_images_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        return CollectionPermissions._is_creator_list(user_obj, qs)

    @staticmethod
    def add_images(user_obj, obj: Collection):
        return CollectionPermissions.add_images_list(user_obj).contains(obj)

    @staticmethod
    def edit_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        return CollectionPermissions._is_creator_list(user_obj, qs)

    @staticmethod
    def edit_collection(user_obj, obj: Collection):
        return CollectionPermissions.add_images_list(user_obj).contains(obj)


Collection.perms_class = CollectionPermissions
