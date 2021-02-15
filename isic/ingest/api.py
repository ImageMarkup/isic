from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from isic.ingest.models import Accession
from isic.ingest.serializers import AccessionSerializer


class AccessionViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccessionSerializer
    queryset = Accession.objects.all()
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['patch'])
    def soft_accept(self, request, pk=None):
        accession = self.get_object()
        serializer = self.get_serializer(accession)
        for key, value in request.data.items():
            if key.endswith('_check') and getattr(accession, key) is None:
                setattr(accession, key, value)
                accession.save(update_fields=[key])
        return Response(serializer.data)
