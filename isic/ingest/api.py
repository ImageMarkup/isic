from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAdminUser

from isic.ingest.models import Accession
from isic.ingest.serializers import AccessionSerializer


class AccessionViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccessionSerializer
    queryset = Accession.objects.all()
    permission_classes = [IsAdminUser]
