from django.urls import reverse
import pytest

from isic.ingest.models.accession import Accession, AccessionState


@pytest.fixture
def accessions(accession_factory, accession_review_factory):
    return [
        accession_review_factory(value=False).accession,
        accession_review_factory(value=False).accession,
        accession_factory(),
        accession_review_factory(value=True).accession,
    ]


@pytest.mark.django_db
def test_api_accession_create(authenticated_client, user, cohort_factory, s3ff_random_field_value):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_creates_accessions_with_unstructured_metadata(
    authenticated_client, user, cohort_factory, s3ff_random_field_value
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1
    assert cohort.accessions.first().unstructured_metadata is not None


@pytest.mark.django_db
def test_api_accession_create_duplicate_blob_name(
    authenticated_client, user, cohort_factory, s3ff_random_field_value
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )
    assert resp.status_code == 400, resp.json()
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_invalid_cohort(
    authenticated_client, user_factory, cohort_factory, s3ff_random_field_value
):
    invalid_cohort = cohort_factory(contributor__creator=user_factory())

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={"cohort": invalid_cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 403, resp.json()


@pytest.mark.django_db
def test_api_accession_create_review_bulk(staff_client, accession_factory):
    accessions = [accession_factory() for _ in range(4)]

    resp = staff_client.post(
        reverse("api:accession_review_bulk_create"),
        data=[{"id": accession.id, "value": True} for accession in accessions],
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.data
    assert Accession.objects.filter(review=None).count() == 0


@pytest.mark.django_db
def test_api_accession_create_with_metadata(
    authenticated_client,
    user,
    cohort_factory,
    engagement_profile_factory,
    s3ff_random_field_value_factory,
    faker,
):
    engagement_profile_factory(user=user)
    cohort = cohort_factory(contributor__owners=[user])
    age = faker.random_int(min=1, max=85)
    sex = faker.random_element(["male", "female"])
    survey_id = faker.uuid4()
    external_id = faker.uuid4()

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={
            "cohort": cohort.pk,
            "original_blob": s3ff_random_field_value_factory(),
            "metadata": {"age": age, "sex": sex, "engagement_survey_id": survey_id},
            "engagement_external_id": external_id,
        },
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.json()

    accession = cohort.accessions.get()
    assert resp.json()["id"] == accession.pk

    assert accession.age == age
    assert accession.sex == sex
    # keys MetadataRow doesn't recognize are kept, rather than dropped or rejected
    assert accession.unstructured_metadata.value == {"engagement_survey_id": survey_id}
    assert accession.metadata_versions.count() == 1
    assert accession.engagement.external_id == external_id
    assert accession.state == AccessionState.PROCESSING

    # a retried upload is rejected rather than duplicated
    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={
            "cohort": cohort.pk,
            "original_blob": s3ff_random_field_value_factory(),
            "engagement_external_id": external_id,
        },
        content_type="application/json",
    )

    assert resp.status_code == 400, resp.json()
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_rejects_invalid_metadata(
    authenticated_client, user, cohort_factory, s3ff_random_field_value, faker
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={
            "cohort": cohort.pk,
            "original_blob": s3ff_random_field_value,
            "metadata": {"sex": faker.pystr()},
        },
        content_type="application/json",
    )

    assert resp.status_code == 400, resp.json()
    assert [error["field"] for error in resp.json()["errors"]] == ["sex"]
    # nothing is left behind when any part of the request fails
    assert cohort.accessions.count() == 0


@pytest.mark.django_db
def test_api_accession_create_rejects_external_id_without_engagement_profile(
    authenticated_client, user, cohort_factory, s3ff_random_field_value, faker
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        reverse("api:accession_create"),
        data={
            "cohort": cohort.pk,
            "original_blob": s3ff_random_field_value,
            "engagement_external_id": faker.uuid4(),
        },
        content_type="application/json",
    )

    assert resp.status_code == 400, resp.json()
    assert cohort.accessions.count() == 0
