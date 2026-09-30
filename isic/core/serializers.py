from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha1
import json
from typing import TYPE_CHECKING, cast

from django.contrib.auth.models import AnonymousUser, User
from django.shortcuts import get_object_or_404
from pyparsing.exceptions import ParseException
from rest_framework import serializers

from isic.core.dsl import SearchQueryParseError, django_parser, es_parser, parse_query
from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects
from isic.core.search import build_elasticsearch_query

if TYPE_CHECKING:
    from isic.core.models.image import ImageQuerySet


class StrictSerializer(serializers.Serializer):
    """A serializer that rejects any field it doesn't declare."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected = sorted(set(data) - set(self.fields))
            if unexpected:
                raise serializers.ValidationError(
                    {field: ["Unexpected field."] for field in unexpected}
                )
        return super().to_internal_value(data)


class CollectionIdsField(serializers.ListField):
    child = serializers.IntegerField()

    def to_internal_value(self, data):
        # a comma delimited string of ids, possibly as the only value of a query parameter
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], str):
            data = data[0]
        if isinstance(data, str):
            data = data.split(",") if data else []
        if not isinstance(data, list) or not data:
            return None
        return super().to_internal_value(data)


class SearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(
        allow_null=True, allow_blank=True, default=None, trim_whitespace=False
    )
    collections = CollectionIdsField(allow_null=True, default=None)

    def validate_query(self, value: str | None):
        if value:
            value = value.strip()
            try:
                parse_query(django_parser, value)
            except ParseException as e:
                # this propagates out of validation rather than becoming a validation error, so
                # it reaches the exception handler and becomes a 400 rather than a 422.
                raise SearchQueryParseError from e
        return value

    def to_token_representation(self, user=None):
        # it's important that user always be generated on the server side and not be passed
        # in as data tm the serializer.
        user = user.pk if user else None

        return {
            "user": user,
            "query": self.validated_data["query"],
            "collections": self.validated_data["collections"],
        }

    def to_cache_key(self, user=None):
        token = self.to_token_representation(user)

        if user is not None:
            # let staff users share the same cache representation
            token["user"] = "staff" if user.is_staff else user.pk

        return sha1(json.dumps(token, sort_keys=True).encode()).hexdigest()  # noqa: S324

    @classmethod
    def from_token_representation(cls, token) -> tuple[User | AnonymousUser, SearchQuerySerializer]:
        user = token.get("user")
        user = get_object_or_404(User, pk=user) if user else AnonymousUser()
        serializer = cls(data={"query": token["query"], "collections": token["collections"]})
        serializer.is_valid(raise_exception=True)
        return user, serializer

    def to_queryset(
        self, user: User | AnonymousUser, qs: ImageQuerySet | None = None
    ) -> ImageQuerySet:
        qs = qs if qs is not None else Image.objects.all()
        query = self.validated_data["query"]
        collections = self.validated_data["collections"]

        if query:
            qs = qs.from_search_query(query)

        if collections:
            qs = qs.filter(
                collections__in=get_visible_objects(
                    user,
                    "core.view_collection",
                    Collection.objects.filter(pk__in=collections),
                )
            )

        return get_visible_objects(user, "core.view_image", qs).distinct()

    def to_es_query(self, user: User | AnonymousUser) -> dict:
        query = self.validated_data["query"]
        es_query: dict | None = None
        if query:
            # we know it can't be a Q object because we're using es_parser and not django_parser
            es_query = cast("dict | None", parse_query(es_parser, query))

        return build_elasticsearch_query(
            es_query or {},
            user,
            self.validated_data["collections"],
        )


class SearchQueryBodySerializer(StrictSerializer, SearchQuerySerializer):
    pass
