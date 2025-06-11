from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test.client import Client
import pytest
from pytest_factoryboy import register

from isic.core.search import (
    IMAGE_INDEX_MAPPINGS,
    LESION_INDEX_MAPPINGS,
    get_elasticsearch_client,
    maybe_create_index,
)
from isic.core.tests.factories import CollectionFactory, DoiFactory, ImageFactory, IsicIdFactory
from isic.ingest.tests.factories import (
    AccessionFactory,
    AccessionReviewFactory,
    CohortFactory,
    ContributorFactory,
    LesionFactory,
    MetadataFileFactory,
    UnstructuredMetadataFactory,
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
def _setup_groups(request):
    # TODO: figure out how to avoid this and how to get serialized_rollback working.
    if "django_db_setup" in request.fixturenames:
        for group_name in ["Public", "ISIC Staff"]:
            Group.objects.get_or_create(name=group_name)

        public = Group.objects.get(name="Public")
        public.user_set.set(User.objects.all())


@pytest.fixture
def _search_index():
    es = get_elasticsearch_client()
    maybe_create_index(settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, IMAGE_INDEX_MAPPINGS)
    maybe_create_index(settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, LESION_INDEX_MAPPINGS)
    yield
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX)
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def authenticated_client(user):
    # Do not use the client fixture, to prevent mutating its state
    client = Client()
    # Do use the user fixture, to allow tests to easily access this user
    client.force_login(user)
    return client


@pytest.fixture
def staff_user(user_factory):
    return user_factory(is_staff=True)


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


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
register(LesionFactory)
register(MetadataFileFactory)
register(UnstructuredMetadataFactory)
register(ZipUploadFactory)

# core factories
register(IsicIdFactory)
register(ImageFactory)
register(CollectionFactory)
register(DoiFactory)

# studies factories
register(QuestionFactory)
register(QuestionChoiceFactory)
register(FeatureFactory)
register(StudyFactory)
register(StudyTaskFactory)
register(AnnotationFactory)
register(ResponseFactory)
register(MarkupFactory)
