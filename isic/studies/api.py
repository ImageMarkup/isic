from oauth2_provider.contrib.rest_framework.permissions import TokenMatchesOASRequirements
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from isic.studies.models import Annotation, Study, StudyTask
from isic.studies.serializers import AnnotationSerializer, StudySerializer, StudyTaskSerializer

REQUIRED_ALTERNATE_SCOPES = {
    'GET': [['read:study']],
    'POST': [['write:study']],
    'PUT': [['write:study']],
    'DELETE': [['write:study']],
}


class StudyTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudyTaskSerializer
    queryset = StudyTask.objects.all()
    permission_classes = [IsAdminUser & TokenMatchesOASRequirements]
    required_alternate_scopes = REQUIRED_ALTERNATE_SCOPES

    swagger_schema = None


class StudyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudySerializer
    queryset = Study.objects.all()
    permission_classes = [IsAdminUser & TokenMatchesOASRequirements]
    required_alternate_scopes = REQUIRED_ALTERNATE_SCOPES

    swagger_schema = None


class AnnotationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnotationSerializer
    queryset = Annotation.objects.all()
    permission_classes = [IsAdminUser & TokenMatchesOASRequirements]
    required_alternate_scopes = REQUIRED_ALTERNATE_SCOPES

    swagger_schema = None
