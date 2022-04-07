from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import IsicObjectPermissionsFilter, get_visible_objects
from isic.core.serializers import CollectionSerializer, IsicIdListSerializer, SearchQuerySerializer
from isic.core.tasks import populate_collection_from_search_task

from .exceptions import Conflict


@method_decorator(
    name='list', decorator=swagger_auto_schema(operation_summary='Return a list of collections.')
)
@method_decorator(
    name='retrieve',
    decorator=swagger_auto_schema(operation_summary='Retrieve a single collection by ID.'),
)
class CollectionViewSet(ReadOnlyModelViewSet):
    serializer_class = CollectionSerializer
    queryset = Collection.objects.all()
    filter_backends = [IsicObjectPermissionsFilter]

    def _enforce_write_checks(self, user: User):
        if not user.has_perm('core.add_images', self.get_object()):
            raise PermissionDenied

        if self.get_object().locked:
            raise Conflict('Collection is locked for changes.')

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='populate-from-search')
    def populate_from_search(self, request, *args, **kwargs):
        self._enforce_write_checks(request.user)
        serializer = SearchQuerySerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)

        if self.get_object().public and serializer.to_queryset().filter(public=False).exists():
            raise Conflict('You are attempting to add private images to a public collection.')

        # Pass data instead of validated_data because the celery task is going to revalidate.
        # This avoids re encoding collections as a comma delimited string.
        populate_collection_from_search_task.delay(kwargs['pk'], request.user.pk, serializer.data)

        # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
        # way to handle this.
        messages.add_message(
            request, messages.INFO, 'Adding images to collection, this may take a few minutes.'
        )
        return Response(status=status.HTTP_202_ACCEPTED)

    # TODO: refactor *-from-list methods
    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='populate-from-list')
    def populate_from_list(self, request, *args, **kwargs):
        self._enforce_write_checks(request.user)
        serializer = IsicIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_images = Image.objects.filter(isic_id__in=serializer.validated_data['isic_ids'])
        visible_images = get_visible_objects(request.user, 'core.view_image', requested_images)
        requested_images = {i.isic_id: i for i in requested_images}
        visible_images = {i.isic_id: i for i in visible_images}
        collection = self.get_object()

        summary = {
            'no_perms_or_does_not_exist': [],
            'private_image_public_collection': [],
            'succeeded': [],
        }

        with transaction.atomic():
            for isic_id in set(serializer.validated_data['isic_ids']):
                if isic_id not in requested_images or isic_id not in visible_images:
                    summary['no_perms_or_does_not_exist'].append(isic_id)
                elif collection.public and visible_images[isic_id].public is False:
                    summary['private_image_public_collection'].append(isic_id)
                else:
                    collection.images.add(visible_images[isic_id])
                    summary['succeeded'].append(isic_id)

        return JsonResponse(summary)

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='remove-from-list')
    def remove_from_list(self, request, *args, **kwargs):
        self._enforce_write_checks(request.user)
        serializer = IsicIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_images = Image.objects.filter(isic_id__in=serializer.validated_data['isic_ids'])
        visible_images = get_visible_objects(request.user, 'core.view_image', requested_images)
        requested_images = {i.isic_id: i for i in requested_images}
        visible_images = {i.isic_id: i for i in visible_images}
        collection = self.get_object()

        summary = {
            'no_perms_or_does_not_exist': [],
            'succeeded': [],
        }

        with transaction.atomic():
            for isic_id in set(serializer.validated_data['isic_ids']):
                if isic_id not in requested_images or isic_id not in visible_images:
                    summary['no_perms_or_does_not_exist'].append(isic_id)
                else:
                    collection.images.remove(visible_images[isic_id])
                    summary['succeeded'].append(isic_id)

        return JsonResponse(summary)

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['delete'], pagination_class=None, url_path='images/delete')
    def delete_images(self, request, *args, **kwargs):
        collection = self.get_object()

        if not request.user.has_perm('core.edit_collection', collection):
            raise PermissionDenied
        elif self.get_object().locked:
            raise Conflict('Collection is locked for changes.')

        serializer = IsicIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        images_to_delete = collection.images.filter(
            isic_id__in=serializer.validated_data['isic_ids']
        )
        collection.images.remove(*images_to_delete)

        # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
        # way to handle this.
        messages.add_message(request, messages.INFO, f'Removed {images_to_delete.count()} images.')
        return JsonResponse({})
