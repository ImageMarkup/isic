from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from isic.ingest.models import Accession, MetadataFile
from isic.ingest.serializers import AccessionSerializer, MetadataFileSerializer
from isic.ingest.tasks import apply_metadata


class AccessionSoftAcceptCheckSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    checks = serializers.ListField(child=serializers.CharField(), required=True)


class AccessionViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccessionSerializer
    queryset = Accession.objects.all()
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_description="Set a check to true if it isn't already set",
        auto_schema=None,
    )
    @action(detail=False, methods=['patch'])
    def soft_accept_check_bulk(self, request, *args, **kwargs):
        serializer = AccessionSoftAcceptCheckSerializer(data=request.data, many=True)
        if serializer.is_valid():
            data_by_id = {x['id']: x['checks'] for x in serializer.data}
            accessions = Accession.objects.filter(id__in=data_by_id.keys())

            with transaction.atomic():
                for accession in accessions:
                    for check in data_by_id[accession.pk]:
                        if getattr(accession, check) is None:
                            setattr(accession, check, True)
                            accession.save(update_fields=[check])

            return Response({})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MetadataFileViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = MetadataFileSerializer
    queryset = MetadataFile.objects.all()
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['post'])
    def apply_metadata(self, request, pk=None):
        metadata_file = self.get_object()
        apply_metadata.delay(metadata_file.id)
        return Response()
