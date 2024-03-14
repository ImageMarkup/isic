import pytest


@pytest.mark.django_db()
def test_metadata_file_to_iterable(metadata_file):
    _, reader = metadata_file.to_iterable()
    next(reader)
