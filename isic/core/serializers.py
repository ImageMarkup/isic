from __future__ import annotations

from typing import cast

from django.contrib.auth.models import AnonymousUser, User
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import field_validator

from isic.core.dsl import es_parser, parse_query
from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects
from isic.core.search import build_elasticsearch_query


class SearchQueryIn(Schema):
    query: str | None = None
    collections: list[int] | None = None

    model_config = {"extra": "forbid"}

    @field_validator("query")
    @classmethod
    def valid_search_query(cls, value: str | None):
        if value:
            value = value.strip()
        return value

    @field_validator("collections", mode="before")
    @classmethod
    def collections_to_list(cls, value: str | list[int]):
        if isinstance(value, str) and value:
            return [int(x) for x in value.split(",")]
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            # TODO: this is a hack to get around the fact that ninja uses a swagger array input
            # field for list types regardless.
            return cls.collections_to_list(value[0])
        if isinstance(value, list) and value:
            return value
        return None

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
    def from_token_representation(cls, token) -> tuple[User, SearchQueryIn]:
        user = token.get("user")
        user = get_object_or_404(User, pk=user) if user else AnonymousUser()
        return user, cls(query=token["query"], collections=token["collections"])

    def to_queryset(self, user: User, qs: QuerySet[Image] | None = None) -> QuerySet[Image]:
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

    def to_es_query(self, user: User) -> dict:
        es_query: dict | None = None
        if self.query:
            # we know it can't be a Q object because we're using es_parser and not django_parser
            es_query = cast(dict | None, parse_query(es_parser, self.query))

        return build_elasticsearch_query(
            es_query or {},
            user,
            self.collections,
        )
