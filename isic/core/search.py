from functools import lru_cache
import logging
from typing import Optional

from django.conf import settings
from django.db.models.query import QuerySet
from elasticsearch.client import Elasticsearch
from elasticsearch.helpers.actions import streaming_bulk

from isic.core.models import Image

logger = logging.getLogger(__name__)

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
    'patient_id': {'terms': {'field': 'patient_id'}},
    'lesion_id': {'terms': {'field': 'lesion_id'}},
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
def get_elasticsearch_client() -> Elasticsearch:
    return Elasticsearch(settings.ISIC_ELASTICSEARCH_URI)


def maybe_create_index() -> None:
    # TODO: include private meta fields (e.g. patient/lesion id)
    get_elasticsearch_client().indices.create(
        index=settings.ISIC_ELASTICSEARCH_INDEX,
        ignore=400,  # ignore status code 400 (index already exists)
        body={
            'mappings': {
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
        },
    )


def add_to_search_index(image: Image) -> None:
    get_elasticsearch_client().index(
        index=settings.ISIC_ELASTICSEARCH_INDEX, body=image.as_elasticsearch_document
    )


def bulk_add_to_search_index(qs: QuerySet[Image], chunk_size: int = 500) -> None:
    # Use a generator for lazy evaluation
    image_documents = (
        image.as_elasticsearch_document
        for image in qs.prefetch_related('accession__upload__cohort__contributor__owners')
        .prefetch_related('shares')
        .all()
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


def facets(query: Optional[dict] = None) -> dict:
    body = {
        'size': 0,
        'aggs': DEFAULT_SEARCH_AGGREGATES,
    }

    if query:
        body['query'] = query

    return get_elasticsearch_client().search(index=settings.ISIC_ELASTICSEARCH_INDEX, body=body)[
        'aggregations'
    ]


def search_images(
    query: Optional[dict] = None,
    limit: Optional[int] = settings.REST_FRAMEWORK['PAGE_SIZE'],
    offset: Optional[int] = 0,
) -> dict:
    # TODO: stably sort by _created
    body = {
        'from': offset,
        'size': limit,
        'fields': ['id'],
        '_source': False,
        'track_total_hits': True,
    }

    if query:
        body['query'] = query

    return get_elasticsearch_client().search(index=settings.ISIC_ELASTICSEARCH_INDEX, body=body)
