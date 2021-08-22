import pytest


@pytest.mark.django_db
def test_accession_generate_thumbnail(accession_factory):
    accession = accession_factory(thumbnail_256=None)

    accession.generate_thumbnail()

    with accession.thumbnail_256.open() as thumbnail_stream:
        thumbnail_content = thumbnail_stream.read()
        assert thumbnail_content.startswith(b'\xff\xd8')
