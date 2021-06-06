from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .image import Image


class Collection(TimeStampedModel):
    images = models.ManyToManyField(Image, related_name='collections')

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('core/collection-detail', args=[self.pk])


class CollectionPermissions:
    model = Collection
    perms = ['view_collection']
    filters = {'view_collection': 'view_collection_list'}

    @staticmethod
    def view_collection_list(user_obj, qs=Collection._default_manager):
        if not user_obj.is_active or not user_obj.is_authenticated:
            return qs.none()

        if user_obj.is_staff:
            return qs

        return qs.none()

    @staticmethod
    def view_collection(user_obj, obj):
        # TODO: use .contains in django 4
        return CollectionPermissions.view_collection_list(user_obj).filter(pk=obj.pk).exists()


Collection.perms_class = CollectionPermissions
