from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from isic.core.admin import StaffReadonlyAdmin


class UserAdmin(BaseUserAdmin, StaffReadonlyAdmin):
    list_select_related = ["profile"]
    list_display = [
        "date_joined",
        "email",
        "first_name",
        "last_name",
        "girder_id",
        "hash_id",
        "is_staff",
    ]
    search_fields = [
        "email",
        "emailaddress__email",
        "first_name",
        "last_name",
        "profile__girder_id",
        "profile__hash_id",
    ]
    search_help_text = "Search by names, email addresses, girder_id, or hash_id."
    ordering = ["-date_joined"]

    @admin.display(ordering="profile__hash_id")
    def hash_id(self, obj):
        return obj.profile.hash_id

    @admin.display(ordering="profile__girder_id")
    def girder_id(self, obj):
        return obj.profile.girder_id


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
