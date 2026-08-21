from django.contrib import admin

from isic.core.admin import StaffReadonlyAdmin
from isic.engagement.models import EmailDomainContributor, EngagementAccession, EngagementProfile


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


@admin.register(EngagementAccession)
class EngagementAccessionAdmin(StaffReadonlyAdmin):
    list_select_related = ["accession__cohort"]
    list_display = ["external_id", "accession"]
    search_fields = ["external_id", "accession__original_blob_name"]
    search_help_text = "Search by the engagement platform's image id or the original filename."

    autocomplete_fields = ["accession"]


@admin.register(EmailDomainContributor)
class EmailDomainContributorAdmin(StaffReadonlyAdmin):
    list_select_related = ["contributor"]
    list_display = ["domain", "contributor", "created"]
    search_fields = ["domain", "contributor__institution_name"]
    search_help_text = "Search by email domain or contributor institution."

    autocomplete_fields = ["contributor"]
    readonly_fields = ["created", "modified"]
