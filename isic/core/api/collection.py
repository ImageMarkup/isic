from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from isic.core.models.collection import Collection
from isic.core.permissions import IsicObjectPermissionsFilter
from isic.core.serializers import CollectionSerializer, IsicIdListSerializer, SearchQuerySerializer
from isic.core.services.collection.image import (
    collection_add_images_from_isic_ids,
    collection_remove_images_from_isic_ids,
)
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
    filter_backends = [IsicObjectPermissionsFilter, DjangoFilterBackend]
    filterset_fields = ['pinned']

    def _enforce_write_checks(self, user: User):
        if self.get_object().locked:
            raise Conflict('Collection is locked for changes.')

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='populate-from-search')
    def populate_from_search(self, request, *args, **kwargs):
        if not request.user.has_perm('core.add_images', self.get_object()):
            raise PermissionDenied

        self._enforce_write_checks(request.user)
        serializer = SearchQuerySerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)

        if self.get_object().public and serializer.to_queryset().private().exists():
            raise Conflict('You are attempting to add private images to a public collection.')

        # Pass data instead of validated_data because the celery task is going to revalidate.
        # This avoids re encoding collections as a comma delimited string.
        transaction.on_commit(
            lambda: populate_collection_from_search_task.delay(
                kwargs['pk'], request.user.pk, serializer.data
            )
        )

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
        if not request.user.has_perm('core.add_images', self.get_object()):
            raise PermissionDenied

        self._enforce_write_checks(request.user)
        serializer = IsicIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        summary = collection_add_images_from_isic_ids(
            user=request.user,
            collection=self.get_object(),
            isic_ids=serializer.validated_data['isic_ids'],
        )

        return JsonResponse(summary)

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='remove-from-list')
    def remove_from_list(self, request, *args, **kwargs):
        if not request.user.has_perm('core.remove_images', self.get_object()):
            raise PermissionDenied

        self._enforce_write_checks(request.user)
        serializer = IsicIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        summary = collection_remove_images_from_isic_ids(
            user=request.user,
            collection=self.get_object(),
            isic_ids=serializer.validated_data['isic_ids'],
        )

        # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
        # way to handle this.
        messages.add_message(request, messages.INFO, f'Removed {len(summary["succeeded"])} images.')

        return JsonResponse(summary)
