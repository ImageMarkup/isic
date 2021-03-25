import pytest
from pytest_factoryboy import register

from .factories import AccessionFactory, CohortFactory, ContributorFactory, ZipFactory
from .zip_streams import zip_stream_duplicates, zip_stream_only_images

register(AccessionFactory)
register(CohortFactory)
register(ContributorFactory)
register(ZipFactory)

# These can't be natively decorated as fixtures, since they're called directly by Factories
zip_stream_only_images = pytest.fixture(zip_stream_only_images)
zip_stream_duplicates = pytest.fixture(zip_stream_duplicates)
