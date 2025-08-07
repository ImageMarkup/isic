import re

from django.contrib.auth.hashers import check_password, make_password
import pytest

from isic.login.models import HASH_ID_REGEX, Profile


def test_girder_password_hasher_encode():
    hashed = make_password("secret", hasher="bcrypt_girder")

    assert hashed.startswith("bcrypt_girder$")


def test_girder_password_hasher_decode_correct():
    hashed = make_password("secret", hasher="bcrypt_girder")

    check = check_password("secret", hashed)

    assert check is True


def test_girder_password_hasher_decode_incorrect():
    hashed = make_password("secret", hasher="bcrypt_girder")

    check = check_password("wrong", hashed)

    assert check is False


@pytest.mark.django_db
def test_user_creation_generates_profile_with_hashid(user_factory):
    user = user_factory()
    profile = Profile.objects.get(user=user)

    assert profile.hash_id
    assert re.match(HASH_ID_REGEX, profile.hash_id)
