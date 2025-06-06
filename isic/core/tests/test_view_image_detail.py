from typing import TYPE_CHECKING

from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf

if TYPE_CHECKING:
    from isic.core.models.image import Image


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "image_", "can_see"),
    [
        (lf("client"), lf("public_image"), True),
        (lf("client"), lf("private_image"), False),
        (lf("authenticated_client"), lf("public_image"), True),
        (lf("authenticated_client"), lf("private_image"), False),
        (lf("staff_client"), lf("public_image"), True),
        (lf("staff_client"), lf("private_image"), True),
    ],
)
def test_core_image_detail(client_, image_, can_see):
    r = client_.get(reverse("core/image-detail", args=[image_.isic_id]))
    assert r.status_code == 200 if can_see else 403


@pytest.fixture
def detailed_image(
    image_factory,
    user_factory,
    study_factory,
    study_task_factory,
    collection_factory,
    reviewed_image_factory,
):
    user = user_factory()

    metadata = {
        "age": 32,
        "lesion_id": "IL_1234567",
        "patient_id": "IP_1234567",
    }

    private_collection = collection_factory(public=False, pinned=True)
    public_collection = collection_factory(public=True, pinned=True)
    private_study = study_factory(public=False)
    public_study = study_factory(public=True)
    main_image: Image = reviewed_image_factory()(
        public=True,
        accession__cohort__contributor__owners=[user],
    )

    # create an image w/ the same longitudinal information
    secondary_image: Image = reviewed_image_factory()(
        public=True,
        accession__cohort__contributor__owners=[user],
    )
    main_image.accession.update_metadata(user, metadata, ignore_image_check=True)
    secondary_image.accession.update_metadata(user, metadata, ignore_image_check=True)

    private_collection.images.add(main_image)
    public_collection.images.add(main_image)

    study_task_factory(annotator=user, study=public_study, image=main_image)
    study_task_factory(annotator=user, study=private_study, image=main_image)

    return main_image


@pytest.mark.django_db
def test_view_image_detail_public(client, detailed_image):
    r = client.get(reverse("core/image-detail", args=[detailed_image.isic_id]))
    assert r.status_code == 200
    assert set(r.context["sections"].keys()) == {"metadata", "studies"}

    assert r.context["unstructured_metadata"] == {}
    assert r.context["metadata_versions"] == []

    assert "age" not in r.context["metadata"]

    assert all(coll.public for coll in r.context["pinned_collections"])
    assert len(r.context["pinned_collections"]) == 1
    assert all(study.public for study in r.context["studies"])
    assert len(r.context["studies"]) == 1

    assert list(r.context["other_patient_images"]) == []
    assert list(r.context["other_lesion_images"]) == []


@pytest.mark.django_db
def test_view_image_detail_uploader(client, detailed_image):
    client.force_login(detailed_image.accession.cohort.contributor.owners.first())

    r = client.get(reverse("core/image-detail", args=[detailed_image.isic_id]))
    assert r.status_code == 200
    assert set(r.context["sections"].keys()) == {"metadata", "studies"}

    assert "unstructured_metadata" in r.context
    # TODO: uploaders can see all metadata added to their images forever?
    assert "metadata_versions" in r.context

    assert "age" not in r.context["metadata"]

    assert all(coll.public for coll in r.context["pinned_collections"])
    assert len(r.context["pinned_collections"]) == 1
    assert all(study.public for study in r.context["studies"])
    assert len(r.context["studies"]) == 1

    assert list(r.context["other_patient_images"]) == []
    assert list(r.context["other_lesion_images"]) == []
