from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from oauth2_provider.decorators import protected_resource
from rest_framework.decorators import api_view

from isic.login.forms import LoginForm
from isic.login.girder import create_girder_token


@api_view(['POST'])
@protected_resource(scopes=['identity'])
def get_girder_token(request):
    return JsonResponse({'token': create_girder_token(request.user.profile.girder_id)})


class IsicLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'login/login.html'
