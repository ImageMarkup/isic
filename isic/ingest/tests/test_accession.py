import os
import pathlib

import pytest

from isic.ingest.models.accession import Accession
from isic.ingest.utils.zip import Blob

data_dir = pathlib.Path(__file__).parent / 'data'


@pytest.fixture
def jpg_blob():
    with open(data_dir / 'ISIC_0000000.jpg', 'rb') as stream:
        yield Blob(
            name='ISIC_0000000.jpg',
            stream=stream,
            size=os.path.getsize(data_dir / 'ISIC_0000000.jpg'),
        )


@pytest.mark.django_db
def test_accession_generate_thumbnail(accession_factory):
    accession = accession_factory(thumbnail_256=None)

    accession.generate_thumbnail()

    with accession.thumbnail_256.open() as thumbnail_stream:
        thumbnail_content = thumbnail_stream.read()
        assert thumbnail_content.startswith(b'\xff\xd8')


@pytest.mark.django_db
def test_accession_without_zip_upload(user, jpg_blob, cohort):
    accession = Accession.from_blob(jpg_blob)
    accession.creator = user
    accession.cohort = cohort
    accession.save()
