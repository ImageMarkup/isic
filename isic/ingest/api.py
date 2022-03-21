from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response

from isic.core.permissions import IsicObjectPermissionsFilter
from isic.ingest.models import Accession, MetadataFile
from isic.ingest.models.check_log import CheckLog
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.ingest.serializers import (
    AccessionChecksSerializer,
    AccessionCreateSerializer,
    AccessionSoftAcceptCheckSerializer,
    CohortSerializer,
    ContributorSerializer,
    MetadataFileSerializer,
)
from isic.ingest.tasks import apply_metadata_task, process_accession_task


class AccessionPermissions(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        if request.method == 'POST':
            if 'cohort' in request.data:
                cohort = get_object_or_404(Cohort, pk=request.data['cohort'])
                return request.user.has_perm('ingest.add_accession', cohort)

        return False


class AccessionViewSet(mixins.UpdateModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Accession.objects.all()
    permission_classes = [AccessionPermissions]

    def get_serializer_class(self):
        if self.action == 'create':
            return AccessionCreateSerializer
        else:
            return AccessionChecksSerializer

    @swagger_auto_schema(
        operation_summary='Create an accession directly.',
        operation_description="""
To create an Accession you must provide an "original_blob" which comports to an S3FileField value.
    """,
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        accession = serializer.save(creator=self.request.user)
        process_accession_task.delay(accession.pk)

    # override method just to disable the auto-schema for it
    @swagger_auto_schema(auto_schema=None)
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # override method just to disable the auto-schema for it
    @swagger_auto_schema(auto_schema=None)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(auto_schema=None)
    def perform_update(self, serializer):
        with transaction.atomic():
            # TODO: figure out how to use update_fields?
            serializer.save()
            for field, value in serializer.validated_data.items():
                if field.endswith('_check'):
                    # TODO: checklogs could be "double set", e.g. a user sets
                    # check foo to true when it's already true, resulting in 2 check log entries.
                    serializer.instance.checklogs.create(
                        creator=serializer.context['request'].user,
                        change_field=field,
                        change_to=value,
                    )

    @swagger_auto_schema(
        operation_description="Set a check to true if it isn't already set",
        auto_schema=None,
    )
    @action(detail=False, methods=['patch'])
    def soft_accept_check_bulk(self, request, *args, **kwargs):
        serializer = AccessionSoftAcceptCheckSerializer(data=request.data, many=True)
        if serializer.is_valid():
            data_by_id = {x['id']: x['checks'] for x in serializer.data}
            accessions = Accession.objects.filter(id__in=data_by_id.keys())
            checks = set(sum(data_by_id.values(), []))

            with transaction.atomic():
                checklogs = []
                accessions_to_update = []
                for accession in accessions:
                    for check in data_by_id[accession.pk]:
                        if getattr(accession, check) is None:
                            setattr(accession, check, True)
                            accessions_to_update.append(accession)
                            checklogs.append(
                                CheckLog(
                                    accession=accession,
                                    creator=request.user,
                                    change_field=check,
                                    change_to=True,
                                )
                            )

                # TODO: this is technically updating all the checks fields when each record may only
                # want to update a specific check field.
                Accession.objects.bulk_update(accessions_to_update, fields=checks)
                CheckLog.objects.bulk_create(checklogs)

            return Response({})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(
    name='create',
    decorator=swagger_auto_schema(operation_summary='Create a cohort.'),
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
    decorator=swagger_auto_schema(operation_summary='Create a contributor.'),
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
    def apply_metadata(self, request, pk=None):
        metadata_file = self.get_object()
        apply_metadata_task.delay(metadata_file.pk)
        return Response(status=status.HTTP_202_ACCEPTED)
