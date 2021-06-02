import io

from isic.ingest.models import DistinctnessMeasure


def test_distinctness_measure_compute_checksum_known():
    """Verify DistinctnessMeasure.compute_checksum for a known input."""
    stream = io.BytesIO(b'foo')

    dm = DistinctnessMeasure.compute_checksum(stream)

    assert dm == '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'


def test_distinctness_measure_compute_checksum_empty():
    """Ensure DistinctnessMeasure.compute_checksum works for empty input."""
    stream = io.BytesIO()

    dm = DistinctnessMeasure.compute_checksum(stream)

    assert dm


def test_distinctness_measure_compute_checksum_seek():
    """Ensure DistinctnessMeasure.compute_checksum resets the stream position."""
    stream = io.BytesIO(b'foo')

    DistinctnessMeasure.compute_checksum(stream)

    assert stream.tell() == 0
