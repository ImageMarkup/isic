from django.http import JsonResponse
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated


@swagger_auto_schema(methods=["PUT"], auto_schema=None)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def accept_terms_of_use(request):
    if not request.user.profile.accepted_terms:
        request.user.profile.accepted_terms = timezone.now()
        request.user.profile.save(update_fields=["accepted_terms"])

    return JsonResponse({})
