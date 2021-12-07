from functools import lru_cache
import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from opensearchpy import NotFoundError, OpenSearch
from opensearchpy.helpers import streaming_bulk

from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.permissions import get_visible_objects

logger = logging.getLogger(__name__)

# TODO: include private meta fields (e.g. patient/lesion id)
INDEX_MAPPINGS = {
    'properties': {
        'created': {'type': 'date'},
        'isic_id': {'type': 'text'},
        'public': {'type': 'boolean'},
        'age_approx': {'type': 'integer'},
        'sex': {'type': 'keyword'},
        'benign_malignant': {'type': 'keyword'},
        'diagnosis': {'type': 'keyword'},
        'diagnosis_confirm_type': {'type': 'keyword'},
        'personal_hx_mm': {'type': 'boolean'},
        'family_hx_mm': {'type': 'boolean'},
        'clin_size_long_diam_mm': {'type': 'float'},
        'melanocytic': {'type': 'boolean'},
        'acquisition_day': {'type': 'float'},
        'marker_pen': {'type': 'boolean'},
        'hairy': {'type': 'boolean'},
        'blurry': {'type': 'boolean'},
        'nevus_type': {'type': 'keyword'},
        'image_type': {'type': 'keyword'},
        'dermoscopic_type': {'type': 'keyword'},
        'anatom_site_general': {'type': 'keyword'},
        'color_tint': {'type': 'keyword'},
        'mel_class': {'type': 'keyword'},
        'mel_mitotic_index': {'type': 'keyword'},
        'mel_thick_mm': {'type': 'float'},
        'mel_type': {'type': 'keyword'},
        'mel_ulcer': {'type': 'boolean'},
    }
}

DEFAULT_SEARCH_AGGREGATES = {
    'diagnosis': {'terms': {'field': 'diagnosis'}},
    'age_approx': {
        'histogram': {
            'field': 'age_approx',
            'interval': 10,
            'extended_bounds': {'min': 0, 'max': 100},
        }
    },
    'sex': {'terms': {'field': 'sex'}},
    'benign_malignant': {'terms': {'field': 'benign_malignant'}},
    'diagnosis_confirm_type': {'terms': {'field': 'diagnosis_confirm_type'}},
    'personal_hx_mm': {'terms': {'field': 'personal_hx_mm'}},
    'family_hx_mm': {'terms': {'field': 'family_hx_mm'}},
    'clin_size_long_diam_mm': {
        'histogram': {
            'field': 'clin_size_long_diam_mm',
            'interval': 10,
            'extended_bounds': {'min': 0, 'max': 110},
        }
    },
    'melanocytic': {'terms': {'field': 'melanocytic'}},
    'acquisition_day': {'terms': {'field': 'acquisition_day'}},
    'marker_pen': {'terms': {'field': 'marker_pen'}},
    'hairy': {'terms': {'field': 'hairy'}},
    'blurry': {'terms': {'field': 'blurry'}},
    'nevus_type': {'terms': {'field': 'nevus_type'}},
    'image_type': {'terms': {'field': 'image_type'}},
    'dermoscopic_type': {'terms': {'field': 'dermoscopic_type'}},
    'anatom_site_general': {'terms': {'field': 'anatom_site_general'}},
    'color_tint': {'terms': {'field': 'color_tint'}},
    'mel_class': {'terms': {'field': 'mel_class'}},
    'mel_mitotic_index': {'terms': {'field': 'mel_mitotic_index'}},
    'mel_thick_mm': {
        'range': {
            'field': 'mel_thick_mm',
            'ranges': [
                {'from': 0.0, 'to': 0.5},
                {'from': 0.5, 'to': 1.0},
                {'from': 1.0, 'to': 1.5},
                {'from': 1.5, 'to': 2.0},
                {'from': 2.0, 'to': 2.5},
                {'from': 2.5, 'to': 3.0},
                {'from': 3.0, 'to': 3.5},
                {'from': 3.5, 'to': 4.0},
                {'from': 4.0, 'to': 4.5},
                {'from': 4.5, 'to': 5.0},
                {'from': 5.0},
            ],
        }
    },
    'mel_type': {'terms': {'field': 'mel_type'}},
    'mel_ulcer': {'terms': {'field': 'mel_ulcer'}},
}


@lru_cache
def get_elasticsearch_client() -> OpenSearch:
    return OpenSearch(settings.ISIC_ELASTICSEARCH_URI)


def maybe_create_index() -> None:
    try:
        indices = get_elasticsearch_client().indices.get(settings.ISIC_ELASTICSEARCH_INDEX)
    except NotFoundError:
        # Need to create
        get_elasticsearch_client().indices.create(
            index=settings.ISIC_ELASTICSEARCH_INDEX, body={'mappings': INDEX_MAPPINGS}
        )
    else:
        # "indices" also contains "settings", which are unspecified by us, so only compare
        # "mappings"
        if indices[settings.ISIC_ELASTICSEARCH_INDEX]['mappings'] != INDEX_MAPPINGS:
            # Existing fields cannot be mutated.
            # TODO: It's possible to add new fields if none of the existing fields are modified.
            # https://www.elastic.co/guide/en/elasticsearch/reference/7.14/indices-put-mapping.html
            raise Exception(
                f'Cannot safely update existing index "{settings.ISIC_ELASTICSEARCH_INDEX}".'
            )
        # Otherwise, the index is up to date; nothing to be done.


def add_to_search_index(image: Image) -> None:
    get_elasticsearch_client().index(
        index=settings.ISIC_ELASTICSEARCH_INDEX, body=image.as_elasticsearch_document
    )


def bulk_add_to_search_index(qs: QuerySet[Image], chunk_size: int = 500) -> None:
    # Use a generator for lazy evaluation
    image_documents = (
        image.as_elasticsearch_document
        for image in qs.prefetch_related('accession__cohort__contributor__owners', 'shares').all()
    )

    for success, info in streaming_bulk(
        client=get_elasticsearch_client(),
        index=settings.ISIC_ELASTICSEARCH_INDEX,
        actions=image_documents,
        # The default chunk_size is 500, but that may be too many models to fit into memory
        chunk_size=chunk_size,
    ):
        if not success:
            logger.error('Failed to insert document into elasticsearch', info)


def facets(query: Optional[dict] = None, collections: Optional[list[int]] = None) -> dict:
    body = {
        'size': 0,
        'aggs': DEFAULT_SEARCH_AGGREGATES,
    }

    if collections is not None:
        # Note this include statement means we can only filter by ~65k collections. See:
        # "By default, Elasticsearch limits the terms query to a maximum of 65,536 terms.
        # You can change this limit using the index.max_terms_count setting."
        body['aggs']['collections'] = {'terms': {'field': 'collections', 'include': collections}}

    if query:
        body['query'] = query

    return get_elasticsearch_client().search(index=settings.ISIC_ELASTICSEARCH_INDEX, body=body)[
        'aggregations'
    ]


def build_elasticsearch_query(
    query: str, user: User, collection_pks: Optional[list[int]] = None
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
                user, 'core.view_collection', Collection.objects.filter(pk__in=collection_pks)
            ).values_list('pk', flat=True)
        )
    else:
        visible_collection_pks = None

    query_dict = {'bool': {}}

    if visible_collection_pks is not None:
        query_dict['bool'].setdefault('filter', {})
        query_dict['bool']['filter']['terms'] = {'collections': visible_collection_pks}

    if query:
        query_dict['bool'].setdefault('must', {})
        query_dict['bool']['must']['query_string'] = {'query': query}

    # Note: permissions here must be also modified in ImagePermissions.view_image_list
    if user.is_anonymous:
        query_dict['bool']['should'] = [{'term': {'public': 'true'}}]
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html#bool-min-should-match
        query_dict['bool']['minimum_should_match'] = 1
    elif not user.is_staff:
        query_dict['bool']['should'] = [
            {'term': {'public': 'true'}},
            {'terms': {'shared_to': [user.pk]}},
            {'terms': {'contributor_owner_ids': [user.pk]}},
        ]
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html#bool-min-should-match
        query_dict['bool']['minimum_should_match'] = 1

    return query_dict


def execute_elasticsearch_query(
    query: dict,
    limit: Optional[int] = settings.REST_FRAMEWORK['PAGE_SIZE'],
    offset: Optional[int] = 0,
) -> dict:
    """
    Execute a query with necessary parameters like sorting and limit/offset.

    query should usually be generated by build_elasticsearch_query.
    """
    body = {
        'fields': ['id'],
        '_source': False,
        'sort': {'created': 'asc'},
    }

    if limit:
        body['size'] = limit

    if offset:
        body['from'] = offset

    if query:
        body['query'] = query

    return get_elasticsearch_client().search(index=settings.ISIC_ELASTICSEARCH_INDEX, body=body)
