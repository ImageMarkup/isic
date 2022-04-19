import os

from django.db import transaction
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from s3_file_field.rest_framework import S3FileSerializerField

from isic.core.permissions import IsicObjectPermissionsFilter
from isic.ingest.models import Accession, MetadataFile
from isic.ingest.models.accession_review import AccessionReview
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.ingest.serializers import CohortSerializer, ContributorSerializer, MetadataFileSerializer
from isic.ingest.service import accession_create, accession_review_bulk_create
from isic.ingest.tasks import update_metadata_task


class AccessionPermissions(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        if request.method == 'POST':
            if 'cohort' in request.data:
                cohort = get_object_or_404(Cohort, pk=request.data['cohort'])
                return request.user.has_perm('ingest.add_accession', cohort)

        return False


class AccessionCreateInputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cohort = serializers.PrimaryKeyRelatedField(queryset=Cohort.objects.all())
    original_blob = S3FileSerializerField()


class AccessionCreateOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ['id']


@method_decorator(
    name='post',
    decorator=swagger_auto_schema(
        operation_summary='Create an Accession.',
        request_body=AccessionCreateInputSerializer,
        responses={201: AccessionCreateOutputSerializer},
    ),
)
class AccessionCreateApi(APIView):
    permission_classes = [AccessionPermissions]

    def post(self, request):
        serializer = AccessionCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accession = accession_create(
            creator=request.user,
            blob_name=os.path.basename(serializer.validated_data['original_blob']),
            **serializer.validated_data,
        )
        return JsonResponse(
            AccessionCreateOutputSerializer(accession), status=status.HTTP_201_CREATED
        )


class AccessionCreateReviewBulkInputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    value = serializers.BooleanField()


@method_decorator(name='post', decorator=swagger_auto_schema(auto_schema=None))
class AccessionCreateReviewBulkApi(APIView):
    permission_classes = [AccessionPermissions]

    def post(self, request):
        serializer = AccessionCreateReviewBulkInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            id_value = {x['id']: x['value'] for x in serializer.validated_data}
            accession_reviews = []
            for accession in Accession.objects.select_related('image').filter(
                pk__in=id_value.keys()
            ):
                accession_reviews.append(
                    AccessionReview(
                        accession=accession,
                        creator=request.user,
                        reviewed_at=timezone.now(),
                        value=id_value[accession.pk],
                    )
                )

            accession_review_bulk_create(accession_reviews=accession_reviews)

        return JsonResponse({}, status=status.HTTP_200_OK)


@method_decorator(
    name='create',
    decorator=swagger_auto_schema(auto_schema=None),
)
@method_decorator(
    name='list', decorator=swagger_auto_schema(operation_summary='Return a list of cohorts.')
)
@method_decorator(
    name='retrieve',
    decorator=swagger_auto_schema(operation_summary='Retrieve a single cohort by ID.'),
)
class CohortViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CohortSerializer
    queryset = Cohort.objects.all()
    filter_backends = [IsicObjectPermissionsFilter]


@method_decorator(
    name='create',
    decorator=swagger_auto_schema(auto_schema=None),
)
@method_decorator(
    name='list', decorator=swagger_auto_schema(operation_summary='Return a list of contributors.')
)
@method_decorator(
    name='retrieve',
    decorator=swagger_auto_schema(operation_summary='Retrieve a single contributor by ID.'),
)
class ContributorViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ContributorSerializer
    queryset = Contributor.objects.all()
    filter_backends = [IsicObjectPermissionsFilter]


class MetadataFileViewSet(
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = MetadataFileSerializer
    queryset = MetadataFile.objects.all()
    permission_classes = [IsAdminUser]

    swagger_schema = None

    def perform_destroy(self, instance):
        # Delete the blob from S3
        instance.blob.delete()
        super().perform_destroy(instance)

    @swagger_auto_schema(auto_schema=None)
    @action(detail=True, methods=['post'])
    def update_metadata(self, request, pk=None):
        metadata_file = self.get_object()
        update_metadata_task.delay(request.user.pk, metadata_file.pk)
        return Response(status=status.HTTP_202_ACCEPTED)
