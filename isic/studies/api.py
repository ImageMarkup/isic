from guardian.shortcuts import get_objects_for_user
from rest_framework import viewsets
from rest_framework.filters import BaseFilterBackend
from rest_framework.permissions import DjangoObjectPermissions

from isic.studies.models import Annotation, Study, StudyTask
from isic.studies.serializers import AnnotationSerializer, StudySerializer, StudyTaskSerializer


class ObjectPermissionsFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return get_objects_for_user(
            request.user,
            f'{queryset.model._meta.app_label}.view_{queryset.model._meta.model_name}',
            queryset,
        )


class StudyTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyTaskSerializer
    queryset = StudyTask.objects.all()
    filter_backends = [ObjectPermissionsFilter]
    permission_classes = [DjangoObjectPermissions]


class StudyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudySerializer
    queryset = Study.objects.all()
    filter_backends = [ObjectPermissionsFilter]
    permission_classes = [DjangoObjectPermissions]


class AnnotationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnotationSerializer
    queryset = Annotation.objects.all()
    filter_backends = [ObjectPermissionsFilter]
    permission_classes = [DjangoObjectPermissions]
