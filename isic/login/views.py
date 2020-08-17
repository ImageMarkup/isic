from django.http import JsonResponse
from oauth2_provider.decorators import protected_resource
from rest_framework.decorators import api_view

from isic.login.girder import create_girder_token


@api_view(['POST'])
@protected_resource(scopes=['identity'])
def get_girder_token(request):
    return JsonResponse({'token': create_girder_token(request.user.profile.girder_id)})
