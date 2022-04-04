from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.query_utils import Q
from django.http.response import JsonResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser

from isic.core.api import Conflict
from isic.core.permissions import IsicObjectPermissionsFilter, get_visible_objects
from isic.studies.models import Annotation, Study, StudyTask
from isic.studies.serializers import (
    AnnotationSerializer,
    StudySerializer,
    StudyTaskAssignmentSerializer,
    StudyTaskSerializer,
)


class StudyTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyTaskSerializer
    queryset = StudyTask.objects.all()
    permission_classes = [IsAdminUser]
    filter_backends = [IsicObjectPermissionsFilter]

    swagger_schema = None


class StudyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudySerializer
    queryset = Study.objects.prefetch_related('questions__choices', 'features').distinct()
    filter_backends = [IsicObjectPermissionsFilter]

    swagger_schema = None

    @action(detail=True, methods=['delete'], pagination_class=None, url_path='delete-tasks')
    def delete_tasks(self, request, *args, **kwargs):
        study: Study = self.get_object()
        if not request.user.has_perm('studies.modify_study', study):
            raise PermissionDenied
        elif study.tasks.filter(annotation__isnull=False).exists():
            raise Conflict('Study has answered questions, tasks cannot be deleted.')
        else:
            # TODO: this will timeout for larger studies
            study.tasks.all().delete()
            return JsonResponse({})

    @action(detail=True, methods=['post'], pagination_class=None, url_path='set-tasks')
    def set_tasks(self, request, *args, **kwargs):
        study: Study = self.get_object()
        if not request.user.has_perm('studies.modify_study', study):
            raise PermissionDenied
        elif study.tasks.filter(annotation__isnull=False).exists():
            raise Conflict('Study has answered questions, tasks cannot be overwritten.')

        serializer = StudyTaskAssignmentSerializer(data=request.data, many=True, max_length=100)
        serializer.is_valid(raise_exception=True)

        isic_ids = [x['isic_id'] for x in serializer.validated_data]
        identifier_filter = Q()
        for data in serializer.validated_data:
            identifier_filter |= Q(profile__hash_id__iexact=data['user_hash_id_or_email'])
            identifier_filter |= Q(email__iexact=data['user_hash_id_or_email'])

        requested_users = (
            User.objects.select_related('profile').filter(is_active=True).filter(identifier_filter)
        )
        # create a lookup dictionary that keys users by their hash id and email
        requested_users_lookup = {}
        for user in requested_users:
            requested_users_lookup[user.profile.hash_id] = user
            requested_users_lookup[user.email] = user

        requested_images = study.collection.images.filter(isic_id__in=isic_ids)
        visible_images = get_visible_objects(
            request.user, 'core.view_image', requested_images
        ).in_bulk(field_name='isic_id')

        summary = {
            'image_no_perms_or_does_not_exist': [],
            'user_does_not_exist': [],
            'succeeded': [],
        }

        with transaction.atomic():
            for task_assignment in serializer.validated_data:
                if task_assignment['user_hash_id_or_email'] not in requested_users_lookup:
                    summary['user_does_not_exist'].append(task_assignment['user_hash_id_or_email'])
                elif task_assignment['isic_id'] not in visible_images:
                    summary['image_no_perms_or_does_not_exist'].append(task_assignment['isic_id'])
                else:
                    StudyTask.objects.create(
                        study=study,
                        annotator=requested_users_lookup[task_assignment['user_hash_id_or_email']],
                        image=visible_images[task_assignment['isic_id']],
                    )
                    summary['succeeded'].append(
                        f'{task_assignment["isic_id"]}/{task_assignment["user_hash_id_or_email"]}'
                    )

        return JsonResponse(summary)


class AnnotationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnotationSerializer
    queryset = Annotation.objects.all()
    permission_classes = [IsAdminUser]
    filter_backends = [IsicObjectPermissionsFilter]

    swagger_schema = None
