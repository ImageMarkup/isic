from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from isic.core.services.collection import collection_create
from isic.ingest.forms import CohortForm
from isic.ingest.services.cohort import cohort_delete


@pytest.mark.django_db
def test_cohort_delete(cohort):
    cohort_delete(cohort=cohort)


@pytest.mark.django_db
def test_cohort_delete_with_published_accessions(cohort, accession_factory, image_factory):
    accession = accession_factory(cohort=cohort)
    accession.image = image_factory(accession=accession)
    accession.image.save()

    with pytest.raises(ValidationError):
        cohort_delete(cohort=cohort)


@pytest.mark.django_db
def test_cohort_list_view(staff_client, cohort, user):
    r = staff_client.get(reverse("cohort-list"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_cohort_detail_view_with_published_and_unpublished_accessions(
    staff_client, cohort, accession_factory, image_factory
):
    # there's a lot of shakiness around rendering accessions with both sponsored and non-sponsored
    # images, so this test checks that both work correctly.
    image_factory(accession__cohort=cohort, public=True)
    accession_factory(cohort=cohort, ingested=True)

    r = staff_client.get(reverse("cohort-detail", args=[cohort.pk]))
    assert r.status_code == 200
    assert len(r.context["accessions"]) == 2


@pytest.mark.django_db
def test_cohort_form_updates_magic_collection_name(cohort_factory, user):
    cohort = cohort_factory(name="foo")

    magic_collection = collection_create(
        creator=user,
        name=f"Publish of {cohort.name}",
        description="",
        public=False,
        locked=True,
    )
    cohort.collection = magic_collection
    cohort.save()

    assert cohort.collection.name == "Publish of foo"

    form_data = {
        "name": "bar",
        "description": cohort.description,
        "default_copyright_license": cohort.default_copyright_license,
        "default_attribution": cohort.default_attribution,
    }
    form = CohortForm(form_data, instance=cohort)
    assert form.is_valid()

    updated_cohort = form.save()

    magic_collection.refresh_from_db()
    assert updated_cohort.name == "bar"
    assert magic_collection.name == "Publish of bar"
