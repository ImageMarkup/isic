from copy import deepcopy
from functools import lru_cache, partial
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from isic_metadata import FIELD_REGISTRY
from opensearchpy import NotFoundError, OpenSearch
from opensearchpy.helpers import parallel_bulk
from opensearchpy.transport import Transport

from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects
from isic.core.utils.logging import LoggingContext

logger = logging.getLogger(__name__)

INDEX_MAPPINGS = {"properties": {}}
DEFAULT_SEARCH_AGGREGATES = {}
COUNTS_AGGREGATES = {}

# TODO: include private meta fields (e.g. patient/lesion id)
for key, definition in FIELD_REGISTRY.items():
    if definition.get("search"):
        INDEX_MAPPINGS["properties"][key] = definition["search"]["es_property"]
        DEFAULT_SEARCH_AGGREGATES[key] = definition["search"]["es_facet"]


# Reserved mappings that can only be set by the archive
# Additional fields here need to update the checks in isic_field on isic-metadata.
INDEX_MAPPINGS["properties"].update(
    {
        "age_approx": {"type": "integer"},
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

DEFAULT_SEARCH_AGGREGATES["copyright_license"] = {"terms": {"field": "copyright_license"}}


DEFAULT_SEARCH_AGGREGATES["age_approx"] = {
    "histogram": {
        "field": "age_approx",
        "interval": 5,
        "extended_bounds": {"min": 0, "max": 85},
    }
}
for key, _ in DEFAULT_SEARCH_AGGREGATES.items():
    COUNTS_AGGREGATES[f"{key}_missing"] = {"missing": {"field": key}}
    COUNTS_AGGREGATES[f"{key}_present"] = {"value_count": {"field": key}}


# These are all approaching 10 unique values, which would require passing a size attribute
# to see them all: nevus_type, anatom_site_general, mel_mitotic_index, mel_type


@lru_cache
def get_elasticsearch_client() -> OpenSearch:
    # TODO: investigate using retryable requests with transport_class
    RetryOnTimeoutTransport = partial(Transport, retry_on_timeout=True)
    return OpenSearch(settings.ISIC_ELASTICSEARCH_URI, transport_class=RetryOnTimeoutTransport)


def maybe_create_index() -> None:
    try:
        indices = get_elasticsearch_client().indices.get(settings.ISIC_ELASTICSEARCH_INDEX)
    except NotFoundError:
        # Need to create
        get_elasticsearch_client().indices.create(
            index=settings.ISIC_ELASTICSEARCH_INDEX, body={"mappings": INDEX_MAPPINGS}
        )
    else:
        # "indices" also contains "settings", which are unspecified by us, so only compare
        # "mappings"
        if indices[settings.ISIC_ELASTICSEARCH_INDEX]["mappings"] != INDEX_MAPPINGS:
            # Existing fields cannot be mutated.
            # TODO: It's possible to add new fields if none of the existing fields are modified.
            # https://www.elastic.co/guide/en/elasticsearch/reference/7.14/indices-put-mapping.html
            raise Exception(
                f'Cannot safely update existing index "{settings.ISIC_ELASTICSEARCH_INDEX}".'
            )
        # Otherwise, the index is up to date; nothing to be done.


def add_to_search_index(image: Image) -> None:
    image = Image.objects.with_elasticsearch_properties().get(pk=image.pk)
    get_elasticsearch_client().index(
        index=settings.ISIC_ELASTICSEARCH_INDEX,
        id=image.pk,
        body=image.to_elasticsearch_document(body_only=True),
    )


def bulk_add_to_search_index(qs: QuerySet[Image], chunk_size: int = 2000) -> None:
    # qs must be generated with with_elasticsearch_properties
    # Use a generator for lazy evaluation
    image_documents = (image.to_elasticsearch_document() for image in qs)

    # The opensearch logger is very noisy when updating records,
    # set it to warning during this operation.
    with LoggingContext(logging.getLogger("opensearch"), level=logging.WARN):
        for success, info in parallel_bulk(
            client=get_elasticsearch_client(),
            index=settings.ISIC_ELASTICSEARCH_INDEX,
            actions=image_documents,
            # The default chunk_size is 2000, but that may be too many models to fit into memory.
            # Note the default chunk_size matches QuerySet.iterator
            chunk_size=chunk_size,
        ):
            if not success:
                logger.error("Failed to insert document into elasticsearch", info)


def facets(query: dict | None = None, collections: list[int] | None = None) -> dict:
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
        index=settings.ISIC_ELASTICSEARCH_INDEX,
        body=counts_body,
    )["aggregations"]

    facets_body = {
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

    if collections is not None:
        # Note this include statement means we can only filter by ~65k collections. See:
        # "By default, Elasticsearch limits the terms query to a maximum of 65,536 terms.
        # You can change this limit using the index.max_terms_count setting."
        facets_body["aggs"]["collections"] = {
            "terms": {"field": "collections", "include": collections}
        }

    if query:
        facets_body["query"] = query

    return get_elasticsearch_client().search(
        index=settings.ISIC_ELASTICSEARCH_INDEX, body=facets_body
    )["aggregations"]


def build_elasticsearch_query(
    query: str, user: User, collection_pks: list[int] | None = None
) -> dict:
    """
    Build an elasticsearch query from a DSL query string, a user, and collection ids.

    collection_pks is the confusing bit here. None indicates the user doesn't want to do any
    filtering of collections. An empty list would instead indicate that the user wants images that
    are in an empty set of collections (aka no images). This is counterintuitive but necessary
    because the list of collection IDs gets filtered by permissions. So if the user requests images
    in collections [1] but don't have access to collection 1 then the user should get 0 results.
    """
    if collection_pks is not None:
        visible_collection_pks = list(
            get_visible_objects(
                user, "core.view_collection", Collection.objects.filter(pk__in=collection_pks)
            ).values_list("pk", flat=True)
        )
    else:
        visible_collection_pks = None

    query_dict = {"bool": {}}

    if visible_collection_pks is not None:
        query_dict["bool"].setdefault("filter", {})
        query_dict["bool"]["filter"]["terms"] = {"collections": visible_collection_pks}

    if query:
        query_dict["bool"].setdefault("must", {})
        query_dict["bool"]["must"]["query_string"] = {"query": query}

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
