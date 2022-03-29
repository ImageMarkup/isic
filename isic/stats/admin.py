from django.contrib import admin
from django.db.models.expressions import F

from isic.stats.models import ImageDownload


@admin.register(ImageDownload)
class ImageDownloadAdmin(admin.ModelAdmin):
    list_display = ['isic_id', 'download_time', 'ip_address']
    list_select_related = ['image']
    search_fields = ['image__isic__id', 'ip_address', 'user_agent']
    search_help_text = 'Search by ISIC ID, IP Address, or User Agent.'

    autocomplete_fields = ['image']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(isic_id=F('image__isic_id'))
        return qs

    @admin.display(ordering='isic_id')
    def isic_id(self, obj: ImageDownload):
        return obj.isic_id
