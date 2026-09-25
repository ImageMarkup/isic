from django.contrib.auth.models import User
from django.urls import path
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from isic.auth import IsAuthenticated
from isic.login.services import accept_terms


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "created",
            "accepted_terms",
            "hash_id",
            "full_name",
        ]

    created = serializers.DateTimeField(source="date_joined")
    accepted_terms = serializers.DateTimeField(source="profile.accepted_terms")
    hash_id = serializers.CharField(source="profile.hash_id")
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj: User) -> str:
        return f"{obj.first_name} {obj.last_name}"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def user_accept_terms(request):
    accept_terms(user=request.user)

    return Response({})


urlpatterns = [
    path("me/", user_me, name="user_me"),
    path("accept-terms/", user_accept_terms, name="user_accept_terms"),
]
