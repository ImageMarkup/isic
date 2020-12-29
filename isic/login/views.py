from urllib.parse import parse_qs, urlparse

from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from oauth2_provider.decorators import protected_resource
from oauth2_provider.models import Application
from rest_framework.decorators import api_view

from isic.login.forms import LoginForm
from isic.login.girder import create_girder_token


@api_view(['POST'])
@protected_resource(scopes=['identity'])
def get_girder_token(request):
    token = create_girder_token(request.user.profile.girder_id)
    return JsonResponse({'token': token})


class IsicLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'login/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        redirect_to = urlparse(self.request.GET.get('next'))
        qs = parse_qs(redirect_to.query)

        if qs.get('client_id'):
            app = get_object_or_404(Application, client_id=qs['client_id'][0])
            context['app_name'] = app.name

        return context
