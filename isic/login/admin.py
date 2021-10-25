from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User


class UserAdmin(BaseUserAdmin):
    list_select_related = ['profile']
    list_display = ['email', 'first_name', 'last_name', 'girder_id', 'is_staff']
    search_fields = ['email', 'profile__girder_id']

    def girder_id(self, obj):
        return obj.profile.girder_id


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
