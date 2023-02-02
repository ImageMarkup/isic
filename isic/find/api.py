from django.http.response import JsonResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from isic.find.find import quickfind_execute


def valid_quickfind_query(value: str) -> None:
    if value.lower() in "isic_":
        # Every image starts with ISIC_, so this would produce
        # far too many results to be meaningful. Force the user
        # to enter more information.
        raise serializers.ValidationError("Query too common.")


class QuickfindSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, min_length=3, validators=[valid_quickfind_query])


@swagger_auto_schema(methods=["GET"], auto_schema=None)
@api_view(["GET"])
@permission_classes([AllowAny])
def quickfind(request):
    serializer = QuickfindSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return JsonResponse(
        quickfind_execute(serializer.validated_data["query"], request.user), safe=False
    )
