import pytest

from .csv_streams import (
    csv_stream_bom_filename_column,
    csv_stream_duplicate_filenames,
    csv_stream_valid,
    csv_stream_without_filename_column,
)
from .zip_streams import zip_stream_duplicates, zip_stream_only_images

# These can't be natively decorated as fixtures, since they're called directly by Factories
zip_stream_only_images = pytest.fixture(zip_stream_only_images)
zip_stream_duplicates = pytest.fixture(zip_stream_duplicates)

csv_stream_valid = pytest.fixture(csv_stream_valid)
csv_stream_without_filename_column = pytest.fixture(csv_stream_without_filename_column)
csv_stream_bom_filename_column = pytest.fixture(csv_stream_bom_filename_column)
csv_stream_duplicate_filenames = pytest.fixture(csv_stream_duplicate_filenames)
