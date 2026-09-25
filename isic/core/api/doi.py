from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from s3_file_field.widgets import S3PlaceholderFile

from isic.auth import IsAuthenticated
from isic.core.models.collection import Collection
from isic.core.models.doi import DraftDoi, DraftDoiRelatedIdentifier
from isic.core.services.collection import update_collection
from isic.core.services.collection.doi import create_collection_draft_doi
from isic.core.tasks import publish_draft_doi_task


class SupplementalFileSerializer(serializers.Serializer):
    blob = serializers.CharField(trim_whitespace=False)
    description = serializers.CharField(allow_blank=True, trim_whitespace=False)


class RelatedIdentifierSerializer(serializers.Serializer):
    relation_type = serializers.CharField(allow_blank=True, trim_whitespace=False)
    related_identifier_type = serializers.CharField(allow_blank=True, trim_whitespace=False)
    related_identifier = serializers.CharField(allow_blank=True, trim_whitespace=False)


class CreateDoiSerializer(serializers.Serializer):
    collection_id = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True, trim_whitespace=False)
    supplemental_files = SupplementalFileSerializer(many=True)
    related_identifiers = RelatedIdentifierSerializer(many=True, default=list)

    def validate_supplemental_files(self, supplemental_files):
        if len(supplemental_files) > 10:
            raise serializers.ValidationError("You can only upload up to 10 supplemental files.")

        if any(not file["description"] for file in supplemental_files):
            raise serializers.ValidationError("All supplemental files must have a description.")

        for file in supplemental_files:
            file["blob"] = S3PlaceholderFile.from_field(file["blob"])
            if file["blob"] is None:
                raise serializers.ValidationError("Invalid S3 file field value.")

        return supplemental_files

    def validate_related_identifiers(self, related_identifiers):
        try:
            DraftDoiRelatedIdentifier.validate_related_identifiers(related_identifiers)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

        return related_identifiers


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def doi_create(request):
    payload = CreateDoiSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    collection = get_object_or_404(Collection, pk=payload.validated_data["collection_id"])

    if not request.user.has_perm("core.create_doi", collection):
        return Response(
            {"error": "You do not have permission to create a DOI."},
            status=status.HTTP_403_FORBIDDEN,
        )

    draft_doi = create_collection_draft_doi(
        user=request.user,
        collection=collection,
        description=payload.validated_data["description"],
        supplemental_files=payload.validated_data["supplemental_files"],
        related_identifiers=payload.validated_data["related_identifiers"],
    )

    return Response({"slug": draft_doi.slug}, status=status.HTTP_201_CREATED)


class UpdateDraftDoiSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True, trim_whitespace=False)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def doi_update_draft(request, draft_doi_slug: str):
    payload = UpdateDraftDoiSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    draft_doi = get_object_or_404(
        DraftDoi.objects.select_related("collection"), slug=draft_doi_slug
    )

    if not request.user.has_perm("core.create_doi", draft_doi.collection):
        return Response(
            {"error": "You do not have permission to update this DOI."},
            status=status.HTTP_403_FORBIDDEN,
        )

    update_collection(
        collection=draft_doi.collection,
        description=payload.validated_data["description"],
        ignore_lock=True,
    )

    return Response({"message": "Draft DOI updated successfully."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def doi_publish_draft(request, draft_doi_slug: str):
    with transaction.atomic():
        draft_doi = get_object_or_404(
            DraftDoi.objects.select_for_update().select_related("collection"), slug=draft_doi_slug
        )

        if not request.user.has_perm("core.create_doi", draft_doi.collection):
            return Response(
                {"error": "You do not have permission to publish this DOI."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if draft_doi.is_publishing:
            return Response(
                {"error": "This DOI is already being published."},
                status=status.HTTP_409_CONFLICT,
            )

        draft_doi.is_publishing = True
        draft_doi.save(update_fields=["is_publishing"])

        publish_draft_doi_task.delay_on_commit(draft_doi.id, request.user.id)

    messages.add_message(request, messages.INFO, "Publishing DOI, this may take several minutes.")

    return Response({"message": "DOI publish task started successfully."})


urlpatterns = [
    path("", doi_create, name="doi_create"),
    path("<draft_doi_slug>/", doi_update_draft, name="doi_update_draft"),
    path("<draft_doi_slug>/publish/", doi_publish_draft, name="doi_publish_draft"),
]
