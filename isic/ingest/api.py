import os

from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.fields import FileField as FileSerializerField
from rest_framework.permissions import AllowAny, BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.permissions import IsicObjectPermissionsFilter, get_visible_objects
from isic.ingest.models import Accession, MetadataFile
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.ingest.serializers import CohortSerializer, ContributorSerializer, MetadataFileSerializer
from isic.ingest.services.accession import accession_create
from isic.ingest.services.accession.review import accession_review_bulk_create
from isic.ingest.tasks import update_metadata_task


class AccessionPermissions(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        if request.method == "POST":
            if "cohort" in request.data:
                cohort = get_object_or_404(Cohort, pk=request.data["cohort"])
                return request.user.has_perm("ingest.add_accession", cohort)

        return False


class S3FileWithSizeSerializerField(FileSerializerField):
    # see S3FileSerializerField for implementation details

    def to_internal_value(self, data):
        # Check the signature and load an S3PlaceholderFile
        file_object = S3PlaceholderFile.from_field(data)
        if file_object is None:
            self.fail("invalid")

        # This checks validity of the file name and size
        file_object = super().to_internal_value(file_object)
        return file_object


class AccessionCreateInputSerializer(serializers.Serializer):
    cohort = serializers.PrimaryKeyRelatedField(queryset=Cohort.objects.all())
    original_blob = S3FileWithSizeSerializerField()


class AccessionCreateOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ["id"]


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Create an Accession.",
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
            original_blob_name=os.path.basename(serializer.validated_data["original_blob"].name),
            original_blob_size=serializer.validated_data["original_blob"].size,
            **serializer.validated_data,
        )
        return HttpResponse(
            AccessionCreateOutputSerializer(accession).data, status=status.HTTP_201_CREATED
        )


class AccessionCreateReviewBulkInputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    value = serializers.BooleanField()


@method_decorator(name="post", decorator=swagger_auto_schema(auto_schema=None))
class AccessionCreateReviewBulkApi(APIView):
    permission_classes = [AccessionPermissions]

    def post(self, request):
        serializer = AccessionCreateReviewBulkInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        accession_review_bulk_create(
            reviewer=request.user,
            accession_ids_values={x["id"]: x["value"] for x in serializer.validated_data},
        )

        return Response({}, status=status.HTTP_201_CREATED)


@method_decorator(
    name="create",
    decorator=swagger_auto_schema(auto_schema=None),
)
@method_decorator(
    name="list", decorator=swagger_auto_schema(operation_summary="Return a list of cohorts.")
)
@method_decorator(
    name="retrieve",
    decorator=swagger_auto_schema(operation_summary="Retrieve a single cohort by ID."),
)
class CohortViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CohortSerializer
    queryset = Cohort.objects.all()
    filter_backends = [IsicObjectPermissionsFilter]


@method_decorator(
    name="create",
    decorator=swagger_auto_schema(auto_schema=None),
)
@method_decorator(
    name="list", decorator=swagger_auto_schema(operation_summary="Return a list of contributors.")
)
@method_decorator(
    name="retrieve",
    decorator=swagger_auto_schema(operation_summary="Retrieve a single contributor by ID."),
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
    @action(detail=True, methods=["post"])
    def update_metadata(self, request, pk=None):
        metadata_file = self.get_object()
        update_metadata_task.delay(request.user.pk, metadata_file.pk)
        return Response(status=status.HTTP_202_ACCEPTED)


class CohortAutocompleteSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, min_length=3)


@swagger_auto_schema(methods=["GET"], auto_schema=None)
@api_view(["GET"])
@permission_classes([AllowAny])
def cohort_autocomplete(request):
    serializer = CohortAutocompleteSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    cohorts = get_visible_objects(
        request.user,
        "ingest.view_cohort",
        Cohort.objects.filter(name__icontains=serializer.validated_data["query"]),
    )
    return JsonResponse(
        CohortSerializer(cohorts[:100], many=True).data,
        safe=False,
    )
