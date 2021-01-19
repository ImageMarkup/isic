from django.contrib import admin
from django.db.models import Count
from django_admin_display import admin_display

from isic.ingest.models import Accession, Cohort, Zip  # , UploadBlob


@admin_display(short_description='Extract zip')
def extract_zip(modeladmin, request, queryset):
    from isic.ingest.tasks import extract_zip as extract_zip_task

    for zip in queryset:
        zip.reset()
        extract_zip_task.delay(zip.id)


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created', 'zips_count']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(zips_count=Count('zips'))
        return qs

    @admin_display(admin_order_field='zips_count')
    def zips_count(self, obj):
        return obj.zips_count


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'blob_name', 'blob_size', 'created', 'cohort', 'status', 'review_status']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('upload__cohort')
        return qs

    @admin_display(short_description='Cohort')
    def cohort(self, obj):
        return obj.upload.cohort


@admin.register(Zip)
class ZipAdmin(admin.ModelAdmin):
    list_display = ['id', 'blob_name', 'blob_size', 'created', 'cohort', 'status']
    list_select_related = ['cohort']
    actions = [extract_zip]


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
