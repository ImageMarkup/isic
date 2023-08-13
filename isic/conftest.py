from django.contrib.auth.models import Group, User
from django.test.client import Client
import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from isic.core.tests.factories import CollectionFactory, ImageFactory
from isic.ingest.tests.factories import (
    AccessionFactory,
    AccessionReviewFactory,
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


@pytest.fixture(autouse=True)
def setup_groups(request):
    # TODO: figure out how to avoid this and how to get serialized_rollback working.
    if "django_db_setup" in request.fixturenames:
        for group_name in ["Public", "ISIC Staff"]:
            Group.objects.get_or_create(name=group_name)

        public = Group.objects.get(name="Public")
        public.user_set.set(User.objects.all())


@pytest.fixture
def api_client() -> APIClient:
    # TODO have this return a django.test.Client instead of DRF's APIClient
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
def eager_celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    yield


# To make pytest-factoryboy fixture creation work properly, all factories must be registered at
# this top-level conftest, since the factories have inter-app references.

# Top-level factories
register(ProfileFactory)
register(UserFactory)

# ingest factories
register(AccessionFactory)
register(AccessionReviewFactory)
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
