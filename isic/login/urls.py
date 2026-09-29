from django.urls import path

from isic.login.views import accept_terms_of_use

urlpatterns = [
    path("terms-of-use/accept/", accept_terms_of_use, name="login/accept-terms"),
]
