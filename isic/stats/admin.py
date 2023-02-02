from django.contrib import admin
from django.db.models.expressions import F

from isic.core.admin import StaffReadonlyAdmin
from isic.stats.models import ImageDownload


class DownloadedWithIsicCliFilter(admin.SimpleListFilter):
    title = 'User Agent'
    parameter_name = 'User Agent'

    def lookups(self, request, model_admin):
        return (
            ('isic_cli', 'ISIC CLI'),
            ('other', 'Other'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'isic_cli':
            return queryset.filter(user_agent__startswith='isic-cli')
        elif value == 'other':
            return queryset.exclude(user_agent__startswith='isic-cli')
        return queryset


@admin.register(ImageDownload)
class ImageDownloadAdmin(StaffReadonlyAdmin):
    list_display = ['isic_id', 'download_time', 'ip_address']
    list_select_related = ['image']
    search_fields = ['image__isic__id', 'ip_address', 'user_agent']
    search_help_text = 'Search by ISIC ID, IP Address, or User Agent.'
    list_filter = [DownloadedWithIsicCliFilter]

    autocomplete_fields = ['image']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(isic_id=F('image__isic_id'))
        return qs

    @admin.display(ordering='isic_id')
    def isic_id(self, obj: ImageDownload):
        return obj.isic_id
