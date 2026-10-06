from django.urls import reverse

from isic.core.models import Image
from isic.core.services import staff_image_metadata_csv
from isic.core.utils.csv import EscapingDictWriter
from isic.core.utils.http import Echo


def test_staff_image_metadata_csv(benchmark_with_memory):
    """Generate the staff CSV of every image's metadata, as its task does, without uploading it."""

    def generate():
        rows = staff_image_metadata_csv(qs=Image.objects.all())
        writer = EscapingDictWriter(Echo(), next(rows))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    benchmark_with_memory(generate)


def test_study_responses_csv(benchmark_with_memory, endpoint, manifest):
    """Download a study's responses. It has 10k, which is typical of production studies."""
    path = reverse("studies/study-download-responses", args=[manifest["public_study"]])
    benchmark_with_memory(endpoint("staff", path))
