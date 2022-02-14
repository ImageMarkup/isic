from django.contrib import messages
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from isic.core.dsl import parse_query
from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import IsicObjectPermissionsFilter, get_visible_objects
from isic.core.search import build_elasticsearch_query, facets
from isic.core.serializers import (
    CollectionSerializer,
    ImageSerializer,
    SearchQuerySerializer,
    UserSerializer,
)
from isic.core.stats import get_archive_stats
from isic.core.tasks import populate_collection


@swagger_auto_schema(
    methods=['GET'], operation_summary='Retrieve statistics about the ISIC Archive'
)
@api_view(['GET'])
@permission_classes([AllowAny])
def stats(request):
    return Response(get_archive_stats())


@swagger_auto_schema(methods=['GET'], operation_summary='Retrieve the currently logged in user.')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_me(request):
    return Response(UserSerializer(request.user).data)


@method_decorator(
    name='list', decorator=swagger_auto_schema(operation_summary='Return a list of images.')
)
@method_decorator(
    name='retrieve',
    decorator=swagger_auto_schema(operation_summary='Retrieve a single image by ISIC ID.'),
)
class ImageViewSet(ReadOnlyModelViewSet):
    serializer_class = ImageSerializer
    queryset = (
        Image.objects.select_related('accession')
        .defer('accession__unstructured_metadata')
        .distinct()
    )
    filter_backends = [IsicObjectPermissionsFilter]
    lookup_field = 'isic_id'

    @swagger_auto_schema(
        operation_summary='Retrieve the facets of a search query.',
        query_serializer=SearchQuerySerializer,
        responses={200: 'A set of facets corresponding to the search query.'},
    )
    @action(detail=False, methods=['get'], pagination_class=None)
    def facets(self, request):
        serializer = SearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        query = build_elasticsearch_query(
            serializer.validated_data.get('query', ''),
            request.user,
            serializer.validated_data.get('collections'),
        )
        # Manually pass the list of visible collection PKs through so buckets with
        # counts of 0 aren't included in the facets output for non-visible collections.
        collection_pks = list(
            get_visible_objects(
                request.user,
                'core.view_collection',
                Collection.objects.values_list('pk', flat=True),
            )
        )
        response = facets(query, collection_pks)

        return Response(response)

    @swagger_auto_schema(
        operation_summary='Search images with a key:value query string.',
        operation_description="""
        The search query uses a simple DSL syntax.

        Some example queries are:
        <pre>
            # Display images diagnosed as melanoma from patients that are approximately 50 years old.
            age_approx:50 AND diagnosis:melanoma
        </pre>
        <pre>
            # Display images from male patients that are approximately 20 to 40 years old.
            age_approx:[20 TO 40] AND sex:male
        </pre>
        <pre>
            # Display images from the anterior, posterior, or lateral torso anatomical site where the diagnosis was confirmed by single image expert consensus.
            anatom_site_general:*torso AND diagnosis_confirm_type:"single image expert consensus"
        </pre>

        The following fields are exposed to the query parameter:
        <ul>
            <li>diagnosis</li>
            <li>age_approx</li>
            <li>sex</li>
            <li>benign_malignant</li>
            <li>diagnosis_confirm_type</li>
            <li>personal_hx_mm</li>
            <li>family_hx_mm</li>
            <li>clin_size_long_diam_mm</li>
            <li>melanocytic</li>
            <li>acquisition_day</li>
            <li>marker_pen</li>
            <li>hairy</li>
            <li>blurry</li>
            <li>nevus_type</li>
            <li>image_type</li>
            <li>dermoscopic_type</li>
            <li>anatom_site_general</li>
            <li>color_tint</li>
            <li>mel_class</li>
            <li>mel_mitotic_index</li>
            <li>mel_thick_mm</li>
            <li>mel_type</li>
            <li>mel_ulcer</li>
        </ul>
        """,  # noqa: E501
        query_serializer=SearchQuerySerializer,
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        serializer = SearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get('query'):
            # the serializer has already validated the query will parse
            qs = self.get_queryset().filter(parse_query(serializer.validated_data['query']))
        else:
            qs = self.get_queryset()

        if serializer.validated_data.get('collections', None):
            qs = qs.filter(
                collections__in=get_visible_objects(
                    request.user,
                    'core.view_collection',
                    Collection.objects.filter(pk__in=serializer.validated_data['collections']),
                )
            )

        qs = get_visible_objects(request.user, 'core.view_image', qs)

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        paginated_response = self.get_paginated_response(serializer.data)

        return paginated_response


@method_decorator(
    name='list', decorator=swagger_auto_schema(operation_summary='Return a list of collections.')
)
@method_decorator(
    name='retrieve',
    decorator=swagger_auto_schema(operation_summary='Retrieve a single collection by ID.'),
)
class CollectionViewSet(ReadOnlyModelViewSet):
    serializer_class = CollectionSerializer
    queryset = Collection.objects.all()
    filter_backends = [IsicObjectPermissionsFilter]

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'], pagination_class=None, url_path='populate-from-search')
    def populate_from_search(self, request, *args, **kwargs):
        if not request.user.has_perm('core.add_images', self.get_object()):
            raise PermissionDenied

        if self.get_object().locked:
            raise ValidationError('Collection is locked for changes.')

        serializer = SearchQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        populate_collection.delay(kwargs['pk'], request.user.pk, serializer.validated_data)

        # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
        # way to handle this.
        messages.add_message(
            request, messages.INFO, 'Adding images to collection, this may take a few minutes.'
        )
        return Response()
