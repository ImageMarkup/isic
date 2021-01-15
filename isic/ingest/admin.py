from django.contrib import admin
from django.utils.safestring import mark_safe
from django_admin_display import admin_display

from isic.ingest.models import Zip, UploadBlob


@admin.register(Zip)
class ZipAdmin(admin.ModelAdmin):
    list_display = ['creator', 'last_updated', 'status', 'zip_name']


@admin.register(UploadBlob)
class UploadBlobAdmin(admin.ModelAdmin):
    list_display = ['upload', 'blob_name', 'completed', 'succeeded']
    list_filter = [('succeeded', admin.BooleanFieldListFilter)]
    readonly_fields = ['thumbnail']
    actions = ['restart_blob_upload']

    def thumbnail(self, obj):
        return mark_safe(f'<img src="{obj.blob.url}" width="300" height="300" />')

    @admin_display(short_description='Restart blob upload')
    def restart_blob_upload(self, request, queryset):
        from isic.ingest.tasks import maybe_upload_blob

        for upload_blob in queryset:
            upload_blob.reset()
            maybe_upload_blob.delay(upload_blob.id)
