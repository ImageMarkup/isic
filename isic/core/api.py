from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from isic.core.models.image import Image
from isic.core.permissions import IsicObjectPermissionsFilter
from isic.core.serializers import ImageSerializer
from isic.core.stats import get_archive_stats


@swagger_auto_schema(
    methods=['GET'], operation_description='Retrieve statistics about the ISIC Archive'
)
@api_view(['GET'])
@permission_classes([AllowAny])
def stats(request):
    return Response(get_archive_stats())


class ImageViewSet(ReadOnlyModelViewSet):
    serializer_class = ImageSerializer
    queryset = (
        Image.objects.select_related('accession').defer('accession__unstructured_metadata').all()
    )
    filter_backends = [IsicObjectPermissionsFilter]
    lookup_field = 'isic_id'
