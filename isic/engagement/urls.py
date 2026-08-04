from django.urls import path

from isic.engagement.views import engagement_user_list

urlpatterns = [
    path("staff/engagement/users/", engagement_user_list, name="engagement/user-list"),
]
