import datetime
import random
import string
from typing import Dict, Optional

from bson import ObjectId
from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database


def get_girder_db() -> Database:
    # Default database name is specified within ISIC_MONGO_URI
    return MongoClient(settings.ISIC_MONGO_URI).get_database()


# Making this function private also makes it easier to mock in testing
def _fetch_girder_user(query: Dict) -> Optional[Dict]:
    girder_user = get_girder_db()['user'].find_one(query)

    # coerce password to string
    if girder_user and isinstance(girder_user['salt'], bytes):
        girder_user['salt'] = girder_user['salt'].decode('utf-8')

    return girder_user


def fetch_girder_user_by_id(girder_user_id: str) -> Optional[Dict]:
    return _fetch_girder_user({'_id': ObjectId(girder_user_id)})


def fetch_girder_user_by_email(email: str) -> Optional[Dict]:
    return _fetch_girder_user({'email': email.lower()})


def create_girder_token(girder_user_id: str) -> str:
    now = datetime.datetime.utcnow()
    token_value = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    get_girder_db()['token'].insert_one(
        {
            '_id': token_value,
            'userId': ObjectId(girder_user_id),
            'created': now,
            'expires': now + datetime.timedelta(days=30.0),
            'scope': ['core.user_auth'],
            'access': {
                'groups': [],
                'users': [{'id': ObjectId(girder_user_id), 'level': 2, 'flags': []}],
            },
        }
    )

    return token_value
