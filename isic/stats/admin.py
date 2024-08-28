from django.contrib import admin

from isic.core.admin import StaffReadonlyAdmin
from isic.stats.models import ImageDownload


class DownloadedWithIsicCliFilter(admin.SimpleListFilter):
    title = "User Agent"
    parameter_name = "User Agent"

    def lookups(self, request, model_admin):
        return (
            ("isic_cli", "ISIC CLI"),
            ("other", "Other"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "isic_cli":
            return queryset.filter(user_agent__startswith="isic-cli")
        if value == "other":
            return queryset.exclude(user_agent__startswith="isic-cli")
        return queryset


@admin.register(ImageDownload)
class ImageDownloadAdmin(StaffReadonlyAdmin):
    list_display = ["image__isic__id", "download_time", "ip_address"]
    list_select_related = ["image"]
    search_fields = ["image__isic__id", "ip_address", "user_agent"]
    search_help_text = "Search by ISIC ID, IP Address, or User Agent."
    list_filter = [DownloadedWithIsicCliFilter]
    # Don't show the full count on filtered admin pages, since it's slow.
    show_full_result_count = False

    autocomplete_fields = ["image"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # .annotate adds a join to the COUNT query which slows down the whole page.
        # .select_related only adds a join to the data selection query.
        return qs.select_related("image")
