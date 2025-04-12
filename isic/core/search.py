from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
import hashlib
import logging
from typing import Any, NotRequired, TypedDict, override

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.db.models.query import QuerySet
from isic_metadata import FIELD_REGISTRY
from isic_metadata.fields import ImageTypeEnum
from opensearchpy import NotFoundError, OpenSearch
from opensearchpy.transport import Transport
import sentry_sdk

from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects
from isic.core.utils.logging import LoggingContext
from isic.ingest.models.accession import Accession
from isic.ingest.models.lesion import Lesion

logger = logging.getLogger(__name__)

IMAGE_INDEX_MAPPINGS = {"properties": {}}
DEFAULT_SEARCH_AGGREGATES = {}
COUNTS_AGGREGATES = {}

for key, definition in FIELD_REGISTRY.items():
    if definition.search:
        IMAGE_INDEX_MAPPINGS["properties"][key] = definition.search.es_property
        DEFAULT_SEARCH_AGGREGATES[key] = definition.search.es_facet


# Reserved mappings that can only be set by the archive
# Additional fields here need to update the checks in isic_field on isic-metadata.
IMAGE_INDEX_MAPPINGS["properties"].update(
    {
        "collections": {"type": "integer"},
        "contributor_owner_ids": {"type": "integer"},
        "created": {"type": "date"},
        "id": {"type": "integer"},
        "isic_id": {"type": "keyword"},
        "copyright_license": {"type": "keyword"},
        "public": {"type": "boolean"},
        "shared_to": {"type": "integer"},
    }
)

for computed_field in Accession.computed_fields:
    IMAGE_INDEX_MAPPINGS["properties"].update(computed_field.es_mappings)
    DEFAULT_SEARCH_AGGREGATES.update(computed_field.es_aggregates)

DEFAULT_SEARCH_AGGREGATES["copyright_license"] = {"terms": {"field": "copyright_license"}}


for key in DEFAULT_SEARCH_AGGREGATES:
    COUNTS_AGGREGATES[f"{key}_missing"] = {"missing": {"field": key}}
    COUNTS_AGGREGATES[f"{key}_present"] = {"value_count": {"field": key}}


# These are all approaching 10 unique values, which would require passing a size attribute
# to see them all: nevus_type, anatom_site_general, mel_mitotic_index, mel_type

LESION_INDEX_MAPPINGS = {
    "properties": {
        "lesion_id": {"type": "keyword"},
        "images": {
            "type": "nested",
            "properties": {
                "isic_id": {"type": "keyword"},
                "public": {"type": "boolean"},
                "contributor_owner_ids": {"type": "integer"},
                "shared_to": {"type": "integer"},
            },
        },
    }
}


class InstrumentedTransport(Transport):
    """A transport that adds caching and retries to the base transport."""

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("retry_on_timeout", True)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _cache_key(  # noqa: PLR0913
        method: str, url: str, params: Any, body: Any, timeout: Any, ignore: Any, headers: Any
    ) -> str:
        return (
            "es:"
            + hashlib.sha256(
                f"{method}:{url}:{params}:{body}:{timeout}:{ignore}:{headers}".encode()
            ).hexdigest()
        )

    @override
    def perform_request(
        self,
        method: str,
        url: str,
        params: Any = None,
        body: Any = None,
        timeout: Any = None,
        ignore: Any = (),
        headers: Any = None,
    ) -> Any:
        is_cacheable = url.endswith(("/_count", "/_search"))

        if is_cacheable:
            cache_key = self._cache_key(method, url, params, body, timeout, ignore, headers)
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

        with sentry_sdk.start_span(op="es"):
            result = super().perform_request(method, url, params, body, timeout, ignore, headers)

        if is_cacheable:
            cache.set(cache_key, result)

        return result


@lru_cache
def get_elasticsearch_client() -> "OpenSearch":
    return OpenSearch(settings.ELASTICSEARCH_URL, transport_class=InstrumentedTransport)


def maybe_create_index(index: str, mappings: Mapping[str, Any]) -> None:
    try:
        indices = get_elasticsearch_client().indices.get(index)
    except NotFoundError:
        # Need to create
        get_elasticsearch_client().indices.create(index=index, body={"mappings": mappings})
    else:
        # "indices" also contains "settings", which are unspecified by us, so only compare
        # "mappings"
        if indices[index]["mappings"] != mappings:
            # Existing fields cannot be mutated.
            # TODO: It's possible to add new fields if none of the existing fields are modified.
            # https://www.elastic.co/guide/en/elasticsearch/reference/7.14/indices-put-mapping.html
            raise Exception(f'Cannot safely update existing index "{index}".')
        # Otherwise, the index is up to date; nothing to be done.


def assert_index_exists(name: str) -> None:
    """
    Assert that an index exists in the elasticsearch cluster.

    This is a rather annoying necessity because elasticsearch supports implicitly creating
    indices on the first write operation. This is bad because it can lead to weird failures
    where the index gets created with the wrong mappings and then subsequent operations fail.
    To curb this we assert the index exists before doing any writes. This is useful for catching
    tests that don't use the _search_index fixture but write to elasticsearch.
    """
    get_elasticsearch_client().indices.get(name)


def add_to_search_index(image: Image) -> None:
    assert_index_exists(settings.ISIC_ELASTICSEARCH_IMAGES_INDEX)

    image = Image.objects.with_elasticsearch_properties().get(pk=image.pk)
    get_elasticsearch_client().index(
        index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
        id=image.pk,
        body=image.to_elasticsearch_document(body_only=True),
    )


def bulk_add_to_search_index(
    index: str, qs: QuerySet[Image | Lesion], chunk_size: int = 2_000
) -> None:
    assert_index_exists(index)
    from opensearchpy.helpers import bulk

    # The opensearch logger is very noisy when updating records,
    # set it to warning during this operation.
    with LoggingContext(logging.getLogger("opensearch"), level=logging.WARNING):
        # qs must be generated with with_elasticsearch_properties
        # Use a generator for lazy evaluation
        documents = (obj.to_elasticsearch_document() for obj in qs.iterator(chunk_size=chunk_size))

        # note we can't use parallel_bulk because the cachalot_disabled context manager
        # is thread local.
        success, info = bulk(
            client=get_elasticsearch_client(),
            index=index,
            actions=documents,
            # The default chunk_size is 2000, but that may be too many models to fit into memory.
            # Note the default chunk_size matches QuerySet.iterator
            chunk_size=chunk_size,
            max_retries=3,
        )

        if not success:
            logger.error("Failed to insert document into elasticsearch: %s", info)


def _prettify_facets(facets: dict[str, Any]) -> dict[str, Any]:
    """Perform some post-processing on the facets to make UI rendering easier."""

    def _strip_superfluous_fields(facets: dict[str, dict]) -> dict[str, dict]:
        for value in facets.values():
            value.pop("doc_count_error_upper_bound", None)
            value.pop("sum_other_doc_count", None)

        return facets

    facets = _strip_superfluous_fields(facets)

    image_type_values = {bucket["key"] for bucket in facets["image_type"]["buckets"]}
    missing_image_type = {x.value for x in ImageTypeEnum} - image_type_values

    for value in missing_image_type:
        facets["image_type"]["buckets"].append({"key": value, "doc_count": 0})

    # sort the values of image_type buckets by the element in the key field
    facets["image_type"]["buckets"] = sorted(
        facets["image_type"]["buckets"],
        key=lambda x: ImageTypeEnum(x["key"])._sort_order_,  # type: ignore[attr-defined]
    )

    return facets


def facets(query: dict | None = None) -> dict:
    """
    Generate the facet counts for a given query.

    This has to perform 2 elasticsearch queries, one for computing the present/absent
    counts for each facet, and another for generating the buckets themselves.
    """
    counts_body = {
        "size": 0,
        "aggs": COUNTS_AGGREGATES,
    }

    if query:
        counts_body["query"] = query

    counts = get_elasticsearch_client().search(
        index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
        body=counts_body,
    )["aggregations"]

    FacetsBody = TypedDict(  # noqa: UP013
        "FacetsBody", {"size": int, "aggs": dict, "query": NotRequired[dict | None]}
    )
    facets_body: FacetsBody = {
        "size": 0,
        "aggs": deepcopy(DEFAULT_SEARCH_AGGREGATES),
    }

    # pass the counts through as metadata in the final aggregation query
    # https://www.elastic.co/guide/en/elasticsearch/reference/8.10/search-aggregations.html#add-metadata-to-an-agg
    for field in facets_body["aggs"]:
        facets_body["aggs"][field]["meta"] = {
            "missing_count": counts[f"{field}_missing"]["doc_count"],
            "present_count": counts[f"{field}_present"]["value"],
        }

    # for term fields (non-ranges), show all facet values even if this query has no
    # matching documents.
    for field in facets_body["aggs"]:
        if "terms" in facets_body["aggs"][field]:
            facets_body["aggs"][field]["terms"]["min_doc_count"] = 0

    if query:
        facets_body["query"] = query

    return _prettify_facets(
        get_elasticsearch_client().search(
            index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, body=facets_body
        )["aggregations"]
    )


def build_elasticsearch_query(
    query: dict, user: User | AnonymousUser, collection_pks: list[int] | None = None
) -> dict:
    """
    Build an elasticsearch query from an elasticsearch query body, a user, and collection ids.

    collection_pks is the confusing bit here. None indicates the user doesn't want to do any
    filtering of collections. An empty list would instead indicate that the user wants images that
    are in an empty set of collections (aka no images). This is counterintuitive but necessary
    because the list of collection IDs gets filtered by permissions. So if the user requests images
    in collections [1] but don't have access to collection 1 then the user should get 0 results.
    """
    if collection_pks is not None:
        visible_collection_pks = list(
            get_visible_objects(
                user,
                "core.view_collection",
                Collection.objects.filter(pk__in=collection_pks),
            ).values_list("pk", flat=True)
        )
    else:
        visible_collection_pks = None

    query_dict: dict = {"bool": {"filter": [query]}} if query else {"bool": {}}

    if visible_collection_pks is not None:
        query_dict["bool"].setdefault("filter", [])
        query_dict["bool"]["filter"].append({"terms": {"collections": visible_collection_pks}})

    # Note: permissions here must be also modified in ImagePermissions.view_image_list
    if user.is_anonymous:
        query_dict["bool"]["should"] = [{"term": {"public": "true"}}]
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html#bool-min-should-match
        query_dict["bool"]["minimum_should_match"] = 1
    elif not user.is_staff:
        query_dict["bool"]["should"] = [
            {"term": {"public": "true"}},
            {"terms": {"shared_to": [user.pk]}},
            {"terms": {"contributor_owner_ids": [user.pk]}},
        ]
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html#bool-min-should-match
        query_dict["bool"]["minimum_should_match"] = 1

    return query_dict
