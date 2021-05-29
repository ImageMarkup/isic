from django.urls import path

from isic.discourse_sso.views import DiscourseSsoLoginView

urlpatterns = [
    path(
        'accounts/login/discourse-sso/', DiscourseSsoLoginView.as_view(), name='discourse-sso-login'
    )
]
