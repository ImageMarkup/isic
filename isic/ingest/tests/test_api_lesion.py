from dataclasses import dataclass
from typing import Literal

from isic_metadata.fields import DiagnosisEnum
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.models.lesion import Lesion


@pytest.mark.django_db
def test_api_lesion_detail(authenticated_client, lesion_factory, image_factory):
    lesion = lesion_factory()
    image_factory(accession__lesion=lesion, public=True)

    resp = authenticated_client.get(f"/api/v2/lesions/{lesion.id}/")
    assert resp.status_code == 200, resp.json()


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_api_lesion(authenticated_client, lesion_factory, image_factory):
    lesion = lesion_factory()
    image_factory(accession__lesion=lesion)

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_api_lesion_ignores_imageless_lesions(authenticated_client, lesion_factory, user):
    # give access to the lesion to ensure this isn't passing due to lack of permissions
    lesion_factory(cohort__contributor__owners=[user])

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
    assert len(resp.json()["results"]) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "image_public_states", "expected_lesion_count"),
    [
        (lf("client"), [True, True], 1),
        (lf("client"), [True, False], 0),
        (lf("client"), [False, False], 0),
        (lf("authenticated_client"), [True, True], 1),
        (lf("authenticated_client"), [True, False], 0),
        (lf("authenticated_client"), [False, False], 0),
        (lf("staff_client"), [True, True], 1),
        (lf("staff_client"), [True, False], 1),
        (lf("staff_client"), [False, False], 1),
    ],
)
@pytest.mark.usefixtures("_search_index")
def test_api_lesion_permissions_public(
    client_,
    image_public_states,
    expected_lesion_count,
    lesion_factory,
    image_factory,
    user_factory,
    user,
):
    other_user = user_factory()
    lesion = lesion_factory(cohort__contributor__owners=[other_user])

    for public in image_public_states:
        image_factory(
            accession__lesion=lesion,
            public=public,
            accession__cohort__contributor__owners=[other_user],
        )

    resp = client_.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
    assert len(resp.json()["results"]) == expected_lesion_count


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_api_lesion_permissions_contributor(
    authenticated_client, lesion_factory, image_factory, contributor
):
    lesion = lesion_factory()
    image_factory(
        accession__lesion=lesion, accession__cohort__contributor=contributor, public=False
    )

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_api_lesion_completeness(client, lesion_factory, image_factory):
    lesion = lesion_factory()
    image = image_factory(
        accession__lesion=lesion,
        accession__short_diagnosis="melanoma",
        accession__acquisition_day=1,
        public=True,
    )

    resp = client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
    assert resp.json()["results"][0]["images_count"] == 1
    assert not resp.json()["results"][0]["longitudinally_monitored"]
    assert resp.json()["results"][0]["index_image_id"] == image.isic_id
    assert (
        resp.json()["results"][0]["outcome_diagnosis"]
        == DiagnosisEnum.malignant_malignant_melanocytic_proliferations_melanoma_melanoma_invasive
    )
    assert resp.json()["results"][0]["outcome_diagnosis_1"] == "Malignant"

    # verify longitudinally_monitored
    image_factory(
        accession__lesion=lesion,
        accession__short_diagnosis="nevus",
        accession__acquisition_day=2,
        public=True,
    )

    resp = client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
    assert resp.json()["results"][0]["images_count"] == 2
    assert resp.json()["results"][0]["longitudinally_monitored"]


@dataclass(frozen=True)
class AccessionMeta:
    id: int
    concomitant_biopsy: bool | None
    acquisition_day: int | None
    diagnosis: Literal["melanoma", "nevus", None]
    image_type: str | None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("accession_a", "accession_b", "expected_lesion_diagnosis"),
    [
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=True,
                acquisition_day=None,
                diagnosis="nevus",
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=True,
                acquisition_day=None,
                diagnosis="melanoma",
                image_type=None,
            ),
            DiagnosisEnum.benign_benign_melanocytic_proliferations_nevus_nevus_spitz,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis="nevus",
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis="melanoma",
                image_type=None,
            ),
            DiagnosisEnum.benign_benign_melanocytic_proliferations_nevus_nevus_spitz,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis="melanoma",
                image_type="tbp",
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis="nevus",
                image_type="dermoscopic",
            ),
            DiagnosisEnum.benign_benign_melanocytic_proliferations_nevus_nevus_spitz,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis=None,
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=False,
                acquisition_day=None,
                diagnosis="melanoma",
                image_type=None,
            ),
            None,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=True,
                acquisition_day=1,
                diagnosis=None,
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=True,
                acquisition_day=None,
                diagnosis="melanoma",
                image_type=None,
            ),
            None,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=1,
                diagnosis="nevus",
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=False,
                acquisition_day=7,
                diagnosis="melanoma",
                image_type=None,
            ),
            DiagnosisEnum.benign_benign_melanocytic_proliferations_nevus_nevus_spitz,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=1,
                diagnosis=None,
                image_type=None,
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=False,
                acquisition_day=7,
                diagnosis="melanoma",
                image_type=None,
            ),
            None,
        ),
        (
            AccessionMeta(
                id=1,
                concomitant_biopsy=False,
                acquisition_day=1,
                diagnosis="melanoma",
                image_type="dermoscopic",
            ),
            AccessionMeta(
                id=2,
                concomitant_biopsy=True,
                acquisition_day=None,
                diagnosis=None,
                image_type=None,
            ),
            None,
        ),
    ],
)
def test_lesion_diagnosis(
    accession_a: AccessionMeta,
    accession_b: AccessionMeta,
    expected_lesion_diagnosis: str,
    lesion_factory,
    image_factory,
):
    lesion = lesion_factory()
    image_factory(
        accession__lesion=lesion,
        accession__concomitant_biopsy=accession_a.concomitant_biopsy,
        accession__acquisition_day=accession_a.acquisition_day,
        accession__short_diagnosis=accession_a.diagnosis,
        accession__image_type=accession_a.image_type,
    )
    image_factory(
        accession__lesion=lesion,
        accession__concomitant_biopsy=accession_b.concomitant_biopsy,
        accession__acquisition_day=accession_b.acquisition_day,
        accession__short_diagnosis=accession_b.diagnosis,
        accession__image_type=accession_b.image_type,
    )

    lesion_with_diagnosis = Lesion.objects.with_total_info().get(id=lesion.id)

    expected_lesion_diagnosis_1 = (
        expected_lesion_diagnosis.split(":")[0] if expected_lesion_diagnosis else None
    )
    assert lesion_with_diagnosis.outcome_diagnosis == expected_lesion_diagnosis
    assert lesion_with_diagnosis.outcome_diagnosis_1 == expected_lesion_diagnosis_1
