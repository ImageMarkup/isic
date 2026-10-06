import csv
import io

from django.contrib.auth.models import User
import pytest

from isic.core.models import Collection, Image
from isic.core.services.collection.image import add_images_to_collection
from isic.ingest.models import Accession, AccessionStatus, Cohort
from isic.ingest.services.accession import update_accession_metadata
from isic.ingest.utils.metadata import (
    validate_archive_consistency,
    validate_csv_format_and_filenames,
    validate_internal_consistency,
)

CSV_ROWS = [1_000, 5_000]


def _metadata_row(i: int) -> dict[str, str]:
    return {
        "age": str(20 + i % 60),
        "sex": "female" if i % 2 else "male",
        "diagnosis": "Benign:Benign melanocytic proliferations:Nevus",
        "anatom_site": "Trunk:Anterior trunk",
        "patient_id": f"benchmark-patient-{i // 10}",
        "lesion_id": f"benchmark-lesion-{i // 2}",
    }


def _metadata_csv(manifest, rows) -> tuple[Cohort, list[dict[str, str]], str]:
    """Return a metadata CSV for the 5k accession ingest cohort, as rows and as text."""
    cohort = Cohort.objects.get(pk=manifest["ingest_cohort"])
    filenames = (
        Accession.objects.filter(cohort=cohort)
        .order_by("pk")
        .values_list("original_blob_name", flat=True)[:rows]
    )
    csv_rows = [{"filename": filename, **_metadata_row(i)} for i, filename in enumerate(filenames)]
    csv_file = io.StringIO()
    writer = csv.DictWriter(csv_file, fieldnames=list(csv_rows[0]))
    writer.writeheader()
    writer.writerows(csv_rows)
    return cohort, csv_rows, csv_file.getvalue()


@pytest.mark.parametrize("images", [1_000, 10_000])
def test_add_images_to_collection(benchmark, manifest, rolled_back, images):
    """Add images to a collection that's shared, which also shares each image."""
    collection = Collection.objects.get(pk=manifest["collections"]["target"])
    qs = Image.objects.filter(
        pk__in=list(Image.objects.order_by("pk").values_list("pk", flat=True)[:images])
    )
    benchmark(rolled_back(lambda: add_images_to_collection(collection=collection, qs=qs)))


@pytest.mark.parametrize("rows", [100, 1_000])
def test_update_accession_metadata(benchmark_with_memory, manifest, rolled_back, rows):
    """Apply a metadata CSV to unpublished accessions."""
    user = User.objects.get(pk=manifest["users"]["staff"])
    accession_ids = (
        Accession.objects.filter(
            cohort_id=manifest["ingest_cohort"], status=AccessionStatus.SUCCEEDED
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:rows]
    )
    metadata = [(pk, _metadata_row(i)) for i, pk in enumerate(accession_ids)]
    benchmark_with_memory(
        rolled_back(lambda: update_accession_metadata(user=user, metadata=metadata))
    )


@pytest.mark.parametrize("rows", CSV_ROWS)
def test_validate_csv_format_and_filenames(benchmark_with_memory, manifest, rows):
    cohort, _, text = _metadata_csv(manifest, rows)
    benchmark_with_memory(
        lambda: validate_csv_format_and_filenames(csv.DictReader(io.StringIO(text)), cohort)
    )


@pytest.mark.parametrize("rows", CSV_ROWS)
def test_validate_internal_consistency(benchmark_with_memory, manifest, rows):
    _, csv_rows, _ = _metadata_csv(manifest, rows)
    benchmark_with_memory(lambda: validate_internal_consistency(csv_rows))


@pytest.mark.parametrize("rows", CSV_ROWS)
def test_validate_archive_consistency(benchmark_with_memory, manifest, rows):
    cohort, _, text = _metadata_csv(manifest, rows)
    benchmark_with_memory(
        lambda: validate_archive_consistency(csv.DictReader(io.StringIO(text)), cohort)
    )
