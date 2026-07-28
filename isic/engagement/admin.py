from django.contrib import admin

from isic.core.admin import StaffReadonlyAdmin
from isic.engagement.models import EngagementProfile


@admin.register(EngagementProfile)
class EngagementProfileAdmin(StaffReadonlyAdmin):
    list_select_related = ["user", "default_contributor", "default_cohort"]
    list_display = ["user", "created", "default_contributor", "default_cohort"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "default_contributor__institution_name",
        "default_cohort__name",
    ]
    search_help_text = "Search by user name/email, contributor institution, or cohort name."

    autocomplete_fields = ["user", "default_contributor", "default_cohort"]
    readonly_fields = ["created"]
