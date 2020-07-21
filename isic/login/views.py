import json
from isic.login.girder import get_girder_user
import datetime
import random
import string
from pymongo.mongo_client import MongoClient
from django.conf import settings
from typing import Dict

from oauth2_provider import views as oauth2_views
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_access_token_model


def _create_girder_token(girder_user: Dict) -> str:
    db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
    now = datetime.datetime.utcnow()
    token_value = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    db['token'].insert_one(
        {
            '_id': token_value,
            'userId': girder_user['_id'],
            'created': now,
            'expires': now + datetime.timedelta(days=30.0),
            'scope': ('core.user_auth',),
        }
    )
    # TODO: What does setUserAccess do?
    return token_value


@method_decorator(csrf_exempt, name="dispatch")
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
                body['girder_token'] = _create_girder_token(get_girder_user(token.user.email))
                body = json.dumps(body)

        return url, headers, body, status
