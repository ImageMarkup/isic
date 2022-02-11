from django.test.client import Client
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model
import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from isic.core.tests.factories import CollectionFactory, ImageFactory
from isic.ingest.tests.factories import (
    AccessionFactory,
    CohortFactory,
    ContributorFactory,
    MetadataFileFactory,
    ZipUploadFactory,
)
from isic.studies.tests.factories import (
    AnnotationFactory,
    FeatureFactory,
    MarkupFactory,
    QuestionChoiceFactory,
    QuestionFactory,
    ResponseFactory,
    StudyFactory,
    StudyTaskFactory,
)

from .factories import ProfileFactory, UserFactory


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(user):
    # Do not use the client fixture, to prevent mutating its state
    client = Client()
    # Do use the user fixture, to allow tests to easily access this user
    client.force_login(user)
    return client


@pytest.fixture
def authenticated_api_client(user) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def staff_user(user_factory):
    return user_factory(is_staff=True)


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def staff_api_client(staff_user) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=staff_user)
    return api_client


@pytest.fixture
def oauth_app(user_factory):
    user = user_factory()
    return get_application_model().objects.create(
        name='Test Application',
        redirect_uris='http://localhost',
        user=user,
        client_type=get_application_model().CLIENT_CONFIDENTIAL,
        authorization_grant_type=get_application_model().GRANT_AUTHORIZATION_CODE,
    )


@pytest.fixture
def oauth_token_client(api_client, oauth_app):
    def f(user, scope='identity'):  # TODO: settings default scope
        token = get_access_token_model().objects.create(
            user=user,
            scope=scope,
            expires=timezone.now() + timezone.timedelta(seconds=300),
            token='some-token',
            application=oauth_app,
        )
        api_client.credentials(Authorization=f'Bearer {token}')
        return api_client

    return f


# To make pytest-factoryboy fixture creation work properly, all factories must be registered at
# this top-level conftest, since the factories have inter-app references.

# Top-level factories
register(ProfileFactory)
register(UserFactory)

# ingest factories
register(AccessionFactory)
register(CohortFactory)
register(ContributorFactory)
register(MetadataFileFactory)
register(ZipUploadFactory)

# core factories
register(ImageFactory)
register(CollectionFactory)

# studies factories
register(QuestionFactory)
register(QuestionChoiceFactory)
register(FeatureFactory)
register(StudyFactory)
register(StudyTaskFactory)
register(AnnotationFactory)
register(ResponseFactory)
register(MarkupFactory)
