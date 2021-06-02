from django.urls import path

from isic.discourse_sso.views import DiscourseSsoRedirectView

urlpatterns = [path('discourse-sso/', DiscourseSsoRedirectView.as_view(), name='discourse-sso')]
