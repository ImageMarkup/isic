from django.http import JsonResponse
from drf_yasg.utils import swagger_auto_schema
from oauth2_provider.decorators import protected_resource
from rest_framework.decorators import api_view

from isic.login.girder import create_girder_token


@swagger_auto_schema(methods=['POST'], operation_summary='Retrieve a token for the legacy API.')
@api_view(['POST'])
@protected_resource(scopes=['identity'])
def get_girder_token(request):
    if not request.user.profile.girder_id:
        raise Exception('Profile has no girder_id', request.user.profile)
    token = create_girder_token(request.user.profile.girder_id)
    return JsonResponse({'token': token})
