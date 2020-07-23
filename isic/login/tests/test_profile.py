from django.core.exceptions import ValidationError
import pytest


def test_profile_validate_girder_password_success(profile_factory):
    profile = profile_factory.build(raw_password='testpassword')
    profile.validate_girder_password('testpassword')


def test_profile_validate_girder_password_missing(profile_factory):
    profile = profile_factory.build(raw_password=None)
    with pytest.raises(ValidationError, match=r'user does not have a password'):
        profile.validate_girder_password('testpassword')


def test_profile_validate_girder_password_wrong(profile_factory):
    profile = profile_factory.build(raw_password='testpassword')
    with pytest.raises(ValidationError, match=r'Login failed\.'):
        profile.validate_girder_password('wrongpassword')


def test_profile_validate_girder_password_inactive(profile_factory):
    profile = profile_factory.build(raw_password='testpassword', user__is_active=False)
    with pytest.raises(ValidationError, match=r'Account is disabled\.'):
        profile.validate_girder_password('testpassword')
