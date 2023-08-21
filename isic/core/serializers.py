import re
from typing import Optional

from django.contrib.auth.models import AnonymousUser, User
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import validator
from pyparsing.exceptions import ParseException
from rest_framework import serializers
from rest_framework.fields import Field

from isic.core.constants import ISIC_ID_REGEX
from isic.core.dsl import parse_query
from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects


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
        raise serializers.ValidationError("Couldn't parse search query.")


class IsicIdListSerializer(serializers.Serializer):
    isic_ids = serializers.ListField(child=serializers.RegexField(ISIC_ID_REGEX), max_length=500)

    def to_queryset(self, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()
        qs = qs.filter(isic_id__in=self.validated_data["isic_ids"])
        return get_visible_objects(self.context["user"], "core.view_image", qs)


# TODO: https://github.com/vitalik/django-ninja/issues/526#issuecomment-1283984292
# Update this to use context for the user once django-ninja supports it
class SearchQueryIn(Schema):
    query: str | None = None
    collections: list[int] | None = None

    @validator("query")
    @classmethod
    def valid_search_query(cls, value: str):
        return value.strip() or None

    @validator("collections", pre=True)
    @classmethod
    def collections_to_list(cls, value: str | list[int]):
        if isinstance(value, str):
            return [int(x) for x in value.split(",")]
        elif isinstance(value, list):
            # TODO: this is a hack to get around the fact that ninja uses a swagger array input
            # field for list types regardless.
            return value

    def to_token_representation(self, user=None):
        # it's important that user always be generated on the server side and not be passed
        # in as data tm the serializer.
        user = user.pk if user else None

        return {
            "user": user,
            "query": self.query,
            "collections": self.collections,
        }

    @classmethod
    def from_token_representation(cls, token):
        user = token.get("user")
        if user:
            user = get_object_or_404(User, pk=user)
        else:
            user = AnonymousUser()
        # TODO
        return cls(data=token, context={"user": user})

    def to_queryset(self, user: User, qs: Optional[QuerySet[Image]] = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if self.query:
            qs = qs.from_search_query(self.query)

        if self.collections:
            qs = qs.filter(
                collections__in=get_visible_objects(
                    user,
                    "core.view_collection",
                    Collection.objects.filter(pk__in=self.collections),
                )
            )

        return get_visible_objects(user, "core.view_image", qs).distinct()


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
        # it's important that user always be generated on the server side and not be passed
        # in as data to the serializer.
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
