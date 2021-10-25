from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .image import Image


class Collection(TimeStampedModel):
    images = models.ManyToManyField(Image, related_name='collections')

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    public = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('core/collection-detail', args=[self.pk])


class CollectionPermissions:
    model = Collection
    perms = ['view_collection']
    filters = {'view_collection': 'view_collection_list'}

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


Collection.perms_class = CollectionPermissions
