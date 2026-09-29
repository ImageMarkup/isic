from allauth.socialaccount.models import SocialAccount
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef

from isic.core.admin import StaffReadonlyAdmin


class HasSocialAccountFilter(admin.SimpleListFilter):
    title = "social account"
    parameter_name = "social_account"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.filter(has_social_account=True)
        if value == "no":
            return queryset.filter(has_social_account=False)
        return queryset


class UserAdmin(BaseUserAdmin, StaffReadonlyAdmin):
    list_select_related = ["profile"]
    list_display = [
        "date_joined",
        "email",
        "first_name",
        "last_name",
        "profile__hash_id",
        "is_staff",
        "social_account",
    ]
    list_filter = [*BaseUserAdmin.list_filter, HasSocialAccountFilter]
    search_fields = [
        "email",
        "emailaddress__email",
        "first_name",
        "last_name",
        "profile__hash_id",
    ]
    search_help_text = "Search by names, email addresses, or hash_id."
    ordering = ["-date_joined"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            has_social_account=Exists(SocialAccount.objects.filter(user=OuterRef("pk")))
        )

    @admin.display(boolean=True, ordering="has_social_account")
    def social_account(self, obj):
        return obj.has_social_account


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
