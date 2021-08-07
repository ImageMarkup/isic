import csv
from datetime import datetime

from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models
from django.db.models import Count
from django.db.models.query import Prefetch
from django.db.models.query_utils import Q
from django.http import HttpResponse
from django.template.defaultfilters import filesizeformat
from django.utils.safestring import mark_safe
from django_json_widget.widgets import JSONEditorWidget
from django_object_actions import DjangoObjectActions
from django_object_actions.utils import takes_instance_or_queryset
from girder_utils.admin import ReadonlyTabularInline

from isic.ingest.models import (
    Accession,
    AccessionStatus,
    CheckLog,
    Cohort,
    Contributor,
    MetadataFile,
    Zip,
)


class CohortInline(ReadonlyTabularInline):
    model = Cohort
    fields = ['id', 'name', 'description', 'creator', 'created']


class AccessionInline(ReadonlyTabularInline):
    model = Accession


class CheckLogInline(ReadonlyTabularInline):
    model = CheckLog
    fields = ['created', 'creator', 'change_field', 'change_to']
    ordering = ['-created']


class MetadataFileInline(ReadonlyTabularInline):
    model = MetadataFile


class ZipInline(ReadonlyTabularInline):
    model = Zip


@admin.register(Contributor)
class ContributorAdmin(admin.ModelAdmin):
    list_select_related = ['creator']
    list_display = ['id', 'institution_name', 'creator', 'created', 'cohorts', 'accessions']
    search_fields = ['institution_name', 'creator__username']

    autocomplete_fields = ['creator', 'owners']
    readonly_fields = ['created', 'modified']
    inlines = [CohortInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            cohorts_count=Count('cohorts', distinct=True),
            accessions_count=Count('cohorts__zips__accessions', distinct=True),
        )
        return qs

    @admin.display(ordering='cohorts_count')
    def cohorts(self, obj):
        return intcomma(obj.cohorts_count)

    @admin.display(ordering='accessions_count')
    def accessions(self, obj):
        return intcomma(obj.accessions_count)


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_select_related = ['creator', 'contributor']
    list_display = [
        'id',
        'name',
        'creator',
        'created',
        'zips',
        'metadata_files',
        'accessions',
        'pending_accessions',
        'skipped_accessions',
        'failed_accessions',
        'successful_accessions',
        'contributor',
    ]
    search_fields = ['name', 'creator__username']
    actions = ['export_file_mapping']

    autocomplete_fields = ['creator', 'contributor']
    readonly_fields = ['created', 'modified']
    inlines = [ZipInline, MetadataFileInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            zips_count=Count('zips', distinct=True),
            metadata_files_count=Count('metadata_files', distinct=True),
            accessions_count=Count('zips__accessions', distinct=True),
            pending_accessions_count=Count(
                'zips__accessions',
                filter=Q(zips__accessions__status=AccessionStatus.CREATING)
                | Q(zips__accessions__status=AccessionStatus.CREATED),
                distinct=True,
            ),
            skipped_accessions_count=Count(
                'zips__accessions',
                filter=Q(zips__accessions__status=AccessionStatus.SKIPPED),
                distinct=True,
            ),
            failed_accessions_count=Count(
                'zips__accessions',
                filter=Q(zips__accessions__status=AccessionStatus.FAILED),
                distinct=True,
            ),
            successful_accessions_count=Count(
                'zips__accessions',
                filter=Q(zips__accessions__status=AccessionStatus.SUCCEEDED),
                distinct=True,
            ),
        )
        return qs

    @admin.display(ordering='zips_count')
    def zips(self, obj):
        return intcomma(obj.zips_count)

    @admin.display(ordering='metadata_files_count')
    def metadata_files(self, obj):
        return intcomma(obj.metadata_files_count)

    @admin.display(ordering='accessions_count')
    def accessions(self, obj):
        return intcomma(obj.accessions_count)

    @admin.display(ordering='pending_accessions_count')
    def pending_accessions(self, obj):
        return intcomma(obj.pending_accessions_count)

    @admin.display(ordering='skipped_accessions_count')
    def skipped_accessions(self, obj):
        return intcomma(obj.skipped_accessions_count)

    @admin.display(ordering='failed_accessions_count')
    def failed_accessions(self, obj):
        return intcomma(obj.failed_accessions_count)

    @admin.display(ordering='successful_accessions_count')
    def successful_accessions(self, obj):
        return intcomma(obj.successful_accessions_count)

    @admin.action(description='Export original file mapping')
    @takes_instance_or_queryset
    def export_file_mapping(self, request, queryset):
        current_time = datetime.utcnow().strftime('%Y-%m-%d')
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'
        ] = f'attachment; filename="cohort_file_mapping_{current_time}.csv"'

        writer = csv.DictWriter(response, ['contributor', 'cohort', 'filename', 'isic_id'])

        writer.writeheader()
        for cohort in queryset.select_related('contributor').prefetch_related(
            Prefetch('zips__accessions', queryset=Accession.objects.select_related('image'))
        ):
            for zip in cohort.zips.all():
                for accession in zip.accessions.all():
                    d = {
                        'contributor': cohort.contributor.institution_name,
                        'cohort': cohort.name,
                        'filename': accession.blob_name,
                        'isic_id': accession.image.isic_id if hasattr(accession, 'image') else '',
                    }
                    writer.writerow(d)
        return response


@admin.register(MetadataFile)
class MetadataFileAdmin(admin.ModelAdmin):
    list_select_related = ['creator', 'cohort']
    list_display = ['id', 'blob_name', 'human_blob_size', 'creator', 'created', 'cohort']
    search_fields = ['blob_name', 'creator__username']

    autocomplete_fields = ['creator', 'cohort']
    readonly_fields = ['created', 'modified', 'blob_name', 'human_blob_size']

    @admin.display(description='Blob Size', ordering='blob_size')
    def human_blob_size(self, obj):
        return filesizeformat(obj.blob_size)


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_select_related = ['upload__cohort']
    list_display = ['id', 'blob_name', 'human_blob_size', 'created', 'status', 'cohort']
    list_filter = ['status']
    search_fields = ['blob_name', 'girder_id']

    readonly_fields = ['created', 'modified', 'thumbnail_image', 'distinctnessmeasure']
    inlines = [CheckLogInline]
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    @admin.display(description='Blob Size', ordering='blob_size')
    def human_blob_size(self, obj):
        return filesizeformat(obj.blob_size)

    @admin.display(ordering='upload__cohort')
    def cohort(self, obj):
        return obj.upload.cohort

    @admin.display()
    def thumbnail_image(self, obj):
        return mark_safe(f'<img src="{obj.thumbnail.url}" />')


@admin.register(CheckLog)
class CheckLogAdmin(admin.ModelAdmin):
    list_select_related = ['accession', 'creator', 'accession__upload__cohort']
    list_display = ['id', 'cohort', 'accession', 'creator', 'created', 'change_field', 'change_to']
    list_filter = ['change_field', 'change_to']

    autocomplete_fields = ['accession', 'creator']

    @admin.display(description='Cohort')
    def cohort(self, obj):
        return obj.accession.upload.cohort


@admin.register(Zip)
class ZipAdmin(DjangoObjectActions, admin.ModelAdmin):
    list_select_related = ['creator', 'cohort']
    list_display = ['id', 'blob_name', 'human_blob_size', 'creator', 'created', 'status', 'cohort']
    list_filter = ['status']
    search_fields = ['blob_name', 'creator__username']
    actions = ['extract_zip']

    autocomplete_fields = ['creator', 'cohort']
    readonly_fields = ['created', 'modified', 'blob_name', 'human_blob_size']
    change_actions = ['extract_zip']

    @admin.display(description='Blob Size', ordering='blob_size')
    def human_blob_size(self, obj):
        return filesizeformat(obj.blob_size)

    @admin.action(description='Extract zip')
    @takes_instance_or_queryset
    def extract_zip(self, request, queryset):
        from isic.ingest.tasks import extract_zip as extract_zip_task

        for zip in queryset:
            zip.reset()
            extract_zip_task.delay(zip.pk)
