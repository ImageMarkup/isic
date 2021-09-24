import datetime
import hashlib
import random
import string
from typing import Optional

from bson import ObjectId
from django.conf import settings
from django.contrib.auth.hashers import make_password
from pymongo import MongoClient
from pymongo.database import Database


def get_girder_db() -> Database:
    # Default database name is specified within ISIC_MONGO_URI
    return MongoClient(settings.ISIC_MONGO_URI).get_database()


# Making this function private also makes it easier to mock in testing
def _fetch_girder_user(query: dict) -> Optional[dict]:
    girder_user = get_girder_db()['user'].find_one(query)

    # coerce password to string
    if girder_user and isinstance(girder_user['salt'], bytes):
        girder_user['salt'] = girder_user['salt'].decode('utf-8')

    return girder_user


def fetch_girder_user_by_id(girder_user_id: str) -> Optional[dict]:
    return _fetch_girder_user({'_id': ObjectId(girder_user_id)})


def fetch_girder_user_by_email(email: str) -> Optional[dict]:
    return _fetch_girder_user({'email': email.lower()})


def create_girder_user(
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> None:
    insert_result = get_girder_db()['user'].insert_one(
        {
            # Girder user validation prohibits "@" in the "login" field
            'login': email.replace('@', '_'),
            'email': email,
            'firstName': first_name,
            'lastName': last_name,
            'created': datetime.datetime.utcnow(),
            'emailVerified': False,
            'status': 'enabled',
            'admin': False,
            'size': 0,
            'groups': [],
            'groupInvites': [],
            'access': {'users': [], 'groups': []},
            'public': False,
            'salt': make_password(password, hasher='bcrypt_girder').split('$', 1)[1],
            'gravatar_baseUrl': (
                'https://www.gravatar.com/avatar/'
                f'{hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()}?d=identicon'
            ),
        }
    )

    # Grant the new user ADMIN access to itself
    get_girder_db()['user'].update_one(
        {'_id': insert_result.inserted_id},
        {
            '$addToSet': {
                'access.users': {
                    'id': insert_result.inserted_id,
                    'level': 2,
                    'flags': [],
                }
            }
        },
    )
    # In Girder, the "Study Administrators" group receives read access to this new girder_user,
    # but that requirement is obsolete


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
