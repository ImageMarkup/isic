from django.http import JsonResponse
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from oauth2_provider.decorators import protected_resource
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from isic.login.girder import create_girder_token


@swagger_auto_schema(methods=['POST'], auto_schema=None)
@api_view(['POST'])
@protected_resource(scopes=['identity'])
def get_girder_token(request):
    if not request.user.profile.girder_id:
        raise Exception('Profile has no girder_id', request.user.profile)
    token = create_girder_token(request.user.profile.girder_id)
    return JsonResponse({'token': token})


@swagger_auto_schema(methods=['PUT'], auto_schema=None)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def accept_terms_of_use(request):
    if not request.user.profile.accepted_terms:
        request.user.profile.accepted_terms = timezone.now()
        request.user.profile.save(update_fields=['accepted_terms'])

    return JsonResponse({})
