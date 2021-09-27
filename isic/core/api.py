from django.contrib.auth.models import User
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import IsicObjectPermissionsFilter, get_visible_objects
from isic.core.search import facets, search_images
from isic.core.serializers import ImageSerializer, SearchQuerySerializer
from isic.core.stats import get_archive_stats


@swagger_auto_schema(
    methods=['GET'], operation_description='Retrieve statistics about the ISIC Archive'
)
@api_view(['GET'])
@permission_classes([AllowAny])
def stats(request):
    return Response(get_archive_stats())


def build_filtered_query(user: User, query_params: dict) -> dict:
    """Translate a django search request into an elasticsearch query."""
    serializer = SearchQuerySerializer(data=query_params, context={'user': user})
    serializer.is_valid(raise_exception=True)
    collection_pks = serializer.validated_data.get('collections')
    dsl_query = serializer.validated_data.get('query')

    query_dict = {'bool': {}}

    if collection_pks is not None:
        query_dict['bool'].setdefault('filter', {})
        query_dict['bool']['filter']['terms'] = {'collections': collection_pks}

    if dsl_query:
        query_dict['bool'].setdefault('must', {})
        query_dict['bool']['must']['query_string'] = {'query': dsl_query}

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


class ImageViewSet(ReadOnlyModelViewSet):
    serializer_class = ImageSerializer
    queryset = (
        Image.objects.select_related('accession').defer('accession__unstructured_metadata').all()
    )
    filter_backends = [IsicObjectPermissionsFilter]
    lookup_field = 'isic_id'

    @swagger_auto_schema(
        operation_description='Retrieve the facet counts of a query.',
        query_serializer=SearchQuerySerializer,
    )
    @action(detail=False, methods=['get'], pagination_class=None)
    def facets(self, request):
        query = build_filtered_query(request.user, request.query_params)
        # Manually pass the list of visible collection PKs through so buckets with
        # counts of 0 aren't included in the facets output for non-visible collections.
        collection_pks = list(
            get_visible_objects(
                request.user,
                'core.view_collection',
                Collection.objects.values_list('pk', flat=True),
            )
        )
        return Response(facets(query, collection_pks))

    @swagger_auto_schema(
        operation_description='Search images with a key:value query string.',
        query_serializer=SearchQuerySerializer,
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = build_filtered_query(request.user, request.query_params)
        search_results = search_images(
            query, self.paginator.get_limit(request), self.paginator.get_offset(request)
        )
        isic_ids = [x['fields']['id'][0] for x in search_results['hits']['hits']]
        images = self.get_queryset().filter(pk__in=isic_ids)
        page = self.paginate_queryset(images)
        serializer = self.get_serializer(page, many=True)
        paginated_response = self.get_paginated_response(serializer.data)

        # The count needs to be overriden otherwise the paginator tries to
        # get a count for the queryset (images), which will always be PAGE_SIZE.
        paginated_response.data['count'] = search_results['hits']['total']['value']
        return paginated_response
