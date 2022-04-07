from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from isic.core.serializers import UserSerializer


@swagger_auto_schema(methods=['GET'], operation_summary='Retrieve the currently logged in user.')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_me(request):
    return Response(UserSerializer(request.user).data)
