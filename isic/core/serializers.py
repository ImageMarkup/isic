import re
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from isic_metadata import FIELD_REGISTRY
from pyparsing.exceptions import ParseException
from rest_framework import serializers
from rest_framework.fields import Field

from isic.core.constants import ISIC_ID_REGEX
from isic.core.dsl import parse_query
from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "created",
            "email",
            "full_name",
            "first_name",
            "last_name",
            "hash_id",
            "accepted_terms",
        ]

    created = serializers.DateTimeField(source="date_joined")
    hash_id = serializers.CharField(source="profile.hash_id")
    accepted_terms = serializers.DateTimeField(source="profile.accepted_terms")
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj: User) -> str:
        return f"{obj.first_name} {obj.last_name}"


class CollectionsField(Field):
    """A field for comma separated collection ids."""

    default_error_messages = {
        "invalid": "Not a valid string.",
        "not_comma_delimited": "Not a comma delimited string.",
    }

    def to_representation(self, obj: list[int]) -> str:
        return ",".join([str(element) for element in obj])

    def to_internal_value(self, data: list | str | None) -> list[int] | None:
        if data:
            # if the data is coming from swagger, it's built into a 1 element list
            if isinstance(data, list):
                data = data[0]
            elif not isinstance(data, str):
                self.fail("invalid")

            if not re.match(r"^(\d+)(,\d+)*$", data):
                self.fail("not_comma_delimited")

            data = [int(x) for x in data.split(",")]
            return data


def valid_search_query(value: str) -> None:
    # TODO: this means the DSL query gets parsed twice for /images/search
    try:
        parse_query(value)
    except ParseException:
        raise serializers.ValidationError("Invalid search query.")


class IsicIdListSerializer(serializers.Serializer):
    isic_ids = serializers.ListField(child=serializers.RegexField(ISIC_ID_REGEX), max_length=500)

    def to_queryset(self, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()
        qs = qs.filter(isic_id__in=self.validated_data["isic_ids"])
        return get_visible_objects(self.context["user"], "core.view_image", qs)


class SearchQuerySerializer(serializers.Serializer):
    """A serializer for a search query against images."""

    query = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="A search query string.",
        validators=[valid_search_query],
    )
    collections = CollectionsField(
        required=False,
        help_text="A list of collection IDs to filter a query by, separated with a comma.",
    )

    def to_token_representation(self):
        assert self.is_valid()
        user = None
        if "user" in self.context:
            user = self.context["user"].pk

        return {
            "user": user,
            "query": self.data.get("query", ""),
            "collections": self.data.get("collections", ""),
        }

    @classmethod
    def from_token_representation(cls, token):
        user = token.get("user")
        if user:
            user = get_object_or_404(User, pk=user)
        else:
            user = AnonymousUser()
        return cls(data=token, context={"user": user})

    def to_queryset(self, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if self.validated_data.get("query"):
            # the serializer has already validated the query will parse
            qs = qs.from_search_query(self.validated_data["query"])

        if self.validated_data.get("collections", None):
            qs = qs.filter(
                collections__in=get_visible_objects(
                    self.context["user"],
                    "core.view_collection",
                    Collection.objects.filter(pk__in=self.validated_data["collections"]),
                )
            )

        return get_visible_objects(self.context["user"], "core.view_image", qs).distinct()


class ImageFileSerializer(serializers.Serializer):
    full = serializers.SerializerMethodField()
    thumbnail_256 = serializers.SerializerMethodField()

    def get_full(self, obj: Image) -> dict:
        if settings.DEBUG:
            url = f"https://picsum.photos/seed/{ obj.id }/1000"
        else:
            url = obj.accession.blob.url

        return {
            "url": url,
            "size": obj.accession.blob_size,
        }

    def get_thumbnail_256(self, obj: Image) -> dict:
        # TODO: add a custom setting for using placeholder images
        if settings.DEBUG:
            url = f"https://picsum.photos/seed/{ obj.id }/256"
        else:
            url = obj.accession.thumbnail_256.url

        return {
            "url": url,
            "size": obj.accession.thumbnail_256_size,
        }


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            "isic_id",
            "public",
            "copyright_license",
            "attribution",
            "metadata",
            "files",
        ]

    copyright_license = serializers.CharField(
        source="accession.cohort.copyright_license", read_only=True
    )
    attribution = serializers.CharField(source="accession.cohort.attribution", read_only=True)
    metadata = serializers.SerializerMethodField(read_only=True)
    files = ImageFileSerializer(source="*", read_only=True)

    def get_metadata(self, image: Image) -> dict:
        metadata = {
            "acquisition": {"pixels_x": image.accession.width, "pixels_y": image.accession.height},
            "clinical": {},
        }

        for key, value in image.accession.redacted_metadata.items():
            # this is the only field that we expose that isn't in the FIELD_REGISTRY
            # since it's a derived field.
            if key == "age_approx":
                metadata["clinical"][key] = value
            else:
                metadata[FIELD_REGISTRY[key]["type"]][key] = value

        return metadata


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "description",
            "public",
            "pinned",
            "locked",
            "doi",
        ]

    doi = serializers.URLField(source="doi_url")
