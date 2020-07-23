import json

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider import views as oauth2_views
from oauth2_provider.models import get_access_token_model

from isic.login.girder import create_girder_token


@method_decorator(csrf_exempt, name='dispatch')
class TokenView(oauth2_views.TokenView):
    def create_token_response(self, request):
        url, headers, body, status = super().create_token_response(request)

        if status == 200:
            body = json.loads(body)

            if body.get('access_token'):
                token = (
                    get_access_token_model()
                    .objects.select_related('user')
                    .get(token=body['access_token'])
                )
                body['girder_token'] = create_girder_token(token.user.profile.girder_id)
                body = json.dumps(body)

        return url, headers, body, status
