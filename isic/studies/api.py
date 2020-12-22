from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from isic.studies.models import Annotation, Study, StudyTask
from isic.studies.serializers import AnnotationSerializer, StudySerializer, StudyTaskSerializer


class StudyTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyTaskSerializer
    queryset = StudyTask.objects.all()
    permission_classes = [IsAdminUser]


class StudyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudySerializer
    queryset = Study.objects.all()
    permission_classes = [IsAdminUser]


class AnnotationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnotationSerializer
    queryset = Annotation.objects.all()
    permission_classes = [IsAdminUser]
