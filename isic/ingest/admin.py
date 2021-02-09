from django.contrib import admin
from django.db.models import Count
from django.db.models.query_utils import Q
from django.utils.safestring import mark_safe
from django_admin_display import admin_display
from django_object_actions import DjangoObjectActions
from django_object_actions.utils import takes_instance_or_queryset
from girder_utils.admin import ReadonlyTabularInline

from isic.ingest.models import Accession, Cohort, Zip  # , UploadBlob


class ZipInline(ReadonlyTabularInline):
    model = Zip


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'created',
        'name',
        'zips_count',
        'pending_accessions',
        'skipped_accessions',
        'failed_accessions',
        'successful_accessions',
        'accessions',
    ]
    inlines = [ZipInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            zips_count=Count('zips', distinct=True),
            pending_accessions=Count(
                'zips__accessions',
                filter=Q(zips__accessions__status=Accession.Status.CREATING)
                | Q(zips__accessions__status=Accession.Status.CREATED),
            ),
            skipped_accessions=Count(
                'zips__accessions', filter=Q(zips__accessions__status=Accession.Status.SKIPPED)
            ),
            failed_accessions=Count(
                'zips__accessions', filter=Q(zips__accessions__status=Accession.Status.FAILED)
            ),
            successful_accessions=Count(
                'zips__accessions', filter=Q(zips__accessions__status=Accession.Status.SUCCEEDED)
            ),
            accessions=Count('zips__accessions'),
        )
        return qs

    @admin_display(admin_order_field='zips_count')
    def zips_count(self, obj):
        return obj.zips_count

    @admin_display(admin_order_field='pending_accessions')
    def pending_accessions(self, obj):
        return obj.pending_accessions

    @admin_display(admin_order_field='skipped_accessions')
    def skipped_accessions(self, obj):
        return obj.skipped_accessions

    @admin_display(admin_order_field='failed_accessions')
    def failed_accessions(self, obj):
        return obj.failed_accessions

    @admin_display(admin_order_field='successful_accessions')
    def successful_accessions(self, obj):
        return obj.successful_accessions

    @admin_display(admin_order_field='accessions')
    def accessions(self, obj):
        return obj.accessions


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'blob_name',
        'blob_size',
        'created',
        'cohort',
        'status',
    ]
    readonly_fields = ['original_blob', 'thumbnail']

    search_fields = ['blob_name']

    list_filter = ['status']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('upload__cohort')
        return qs

    @admin_display(short_description='Cohort')
    def cohort(self, obj):
        return obj.upload.cohort

    def thumbnail(self, obj):
        return mark_safe(f'<img src="{obj.blob.url}" width="300" height="300" />')


@admin.register(Zip)
class ZipAdmin(DjangoObjectActions, admin.ModelAdmin):
    list_display = ['id', 'blob_name', 'blob_size', 'created', 'cohort', 'status']
    list_select_related = ['cohort']
    actions = ['extract_zip']
    change_actions = ['extract_zip']

    @admin_display(short_description='Extract zip')
    @takes_instance_or_queryset
    def extract_zip(self, request, queryset):
        from isic.ingest.tasks import extract_zip as extract_zip_task

        for zip in queryset:
            zip.reset()
            extract_zip_task.delay(zip.id)


# @admin.register(UploadBlob)
# class UploadBlobAdmin(admin.ModelAdmin):
#     list_display = ['upload', 'blob_name', 'completed', 'succeeded']
#     list_filter = [('succeeded', admin.BooleanFieldListFilter)]
#     readonly_fields = ['thumbnail']
#     actions = ['restart_blob_upload']
#
#     def thumbnail(self, obj):
#         return mark_safe(f'<img src="{obj.blob.url}" width="300" height="300" />')
#
#     @admin_display(short_description='Restart blob upload')
#     def restart_blob_upload(self, request, queryset):
#         from isic.ingest.tasks import maybe_upload_blob
#
#         for upload_blob in queryset:
#             upload_blob.reset()
#             maybe_upload_blob.delay(upload_blob.id)
