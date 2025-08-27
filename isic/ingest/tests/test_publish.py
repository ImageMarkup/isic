import pathlib

from django.core.files import File
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.urls.base import reverse
from django.utils import timezone
import pyexiv2
import pytest
from resonant_utils.files import field_file_to_local_path

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.views.doi import LICENSE_URIS
from isic.ingest.models.accession import AccessionStatus
from isic.ingest.services.accession import accession_create
from isic.ingest.services.publish import (
    accession_publish,
    cohort_publish_initialize,
    embed_iptc_metadata,
)

data_dir = pathlib.Path(__file__).parent / "data"


@pytest.fixture
def publishable_cohort(cohort_factory, accession_factory, accession_review_factory, user):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    # Make a 'publishable' accession
    accession_review_factory(
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    accession_factory(cohort=cohort, status=AccessionStatus.SKIPPED)
    return cohort


@pytest.fixture
def publishable_cohort_for_attributions(
    cohort_factory, accession_factory, accession_review_factory, user
):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    # Make publishable accessions, one with an attribution, one without
    accession_review_factory(
        accession__attribution="has an attribution",
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    accession_review_factory(
        accession__attribution="",
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    return cohort


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_publish_copies_default_attribution(
    publishable_cohort_for_attributions,
    user,
    django_capture_on_commit_callbacks,
):
    assert set(
        publishable_cohort_for_attributions.accessions.values_list("attribution", flat=True)
    ) == {"has an attribution", ""}

    publishable_cohort_for_attributions.default_attribution = "default attribution"
    publishable_cohort_for_attributions.save(update_fields=["default_attribution"])

    with django_capture_on_commit_callbacks(execute=True):
        cohort_publish_initialize(
            cohort=publishable_cohort_for_attributions,
            publisher=user,
            public=True,
        )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort_for_attributions)

    assert published_images.count() == 2
    assert set(published_images.values_list("accession__attribution", flat=True)) == {
        "has an attribution",
        "default attribution",
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_publish_cohort(
    staff_client, publishable_cohort, django_capture_on_commit_callbacks, collection_factory
):
    collection_a = collection_factory(public=False)
    collection_b = collection_factory(public=False)

    with django_capture_on_commit_callbacks(execute=True):
        staff_client.post(
            reverse("upload/cohort-publish", args=[publishable_cohort.pk]),
            {"private": True, "additional_collections": [collection_a.pk, collection_b.pk]},
        )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort)

    assert published_images.count() == 1
    assert not published_images.first().public  # type: ignore[union-attr]
    assert Collection.objects.count() == 3
    publishable_cohort.refresh_from_db()
    magic_collection = publishable_cohort.collection
    assert not magic_collection.public
    assert magic_collection.locked

    for collection in [collection_a, collection_b]:
        assert collection.images.count() == 1


@pytest.mark.django_db
def test_publish_cohort_into_public_collection(
    staff_client, publishable_cohort, django_capture_on_commit_callbacks, collection_factory
):
    public_collection = collection_factory(public=True)

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("upload/cohort-publish", args=[publishable_cohort.pk]),
            {"private": True, "additional_collections": [public_collection.pk]},
        )
        assert (
            "add private images into a public collection" in r.context["form"].errors["__all__"][0]
        )


@pytest.mark.django_db(transaction=True)
def test_unembargo_images(user, cohort_factory, django_capture_on_commit_callbacks):
    blob_path = pathlib.Path(data_dir / "ISIC_0000000.jpg")
    blob_name = "ISIC_0000000.jpg"

    cohort = cohort_factory(creator=user, contributor__creator=user)
    with blob_path.open("rb") as stream:
        blob = InMemoryUploadedFile(stream, None, blob_name, None, blob_path.stat().st_size, None)
        accession = accession_create(
            creator=user,
            cohort=cohort,
            original_blob=blob,
            original_blob_name=blob_name,
            original_blob_size=blob_path.stat().st_size,
        )
    accession.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        accession_publish(accession=accession, public=True, publisher=user)

    image = Image.objects.get(accession=accession)

    assert image.public
    assert image.accession.sponsored_blob.name == f"images/{image.isic_id}.{image.extension}"
    assert (
        image.accession.sponsored_thumbnail_256_blob.name
        == f"thumbnails/{image.isic_id}_thumbnail.jpg"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("blob_path", "blob_name"),
    [
        (pathlib.Path(data_dir / "ISIC_0000000.jpg"), "ISIC_0000000.jpg"),
        (pathlib.Path(data_dir / "RCM_tile_with_exif.png"), "RCM_tile_with_exif.png"),
    ],
    ids=["jpg_image", "rcm_image"],
)
def test_iptc_metadata_embedding(
    blob_path, blob_name, user, cohort_factory, django_capture_on_commit_callbacks
):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    with blob_path.open("rb") as stream:
        blob = InMemoryUploadedFile(stream, None, blob_name, None, blob_path.stat().st_size, None)
        accession = accession_create(
            creator=user,
            cohort=cohort,
            original_blob=blob,
            original_blob_name=blob_name,
            original_blob_size=blob_path.stat().st_size,
        )
    accession.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        accession_publish(accession=accession, public=False, publisher=user)

    image = Image.objects.get(accession=accession)
    assert not image.public

    for blob in [image.accession.blob, image.accession.thumbnail_256]:
        with (
            field_file_to_local_path(blob) as path,
            pyexiv2.Image(str(path.absolute())) as image_file,
        ):
            # non JPG files should not have IPTC metadata embedded
            if not blob.name.endswith(".jpg"):
                iptc_data = image_file.read_iptc()
                xmp_data = image_file.read_xmp()
                assert iptc_data == {}
                assert xmp_data == {}
            else:
                # For JPEG files, metadata should be present
                assert image_file.read_iptc() == {
                    "Iptc.Application2.Credit": image.accession.attribution,
                    "Iptc.Application2.Source": "ISIC Archive",
                    "Iptc.Envelope.CharacterSet": "\x1b%G",
                }
                # see https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#lang-alt-value-type
                assert image_file.read_xmp()["Xmp.dc.title"] == {'lang="x-default"': image.isic_id}
                assert (
                    image_file.read_xmp()["Xmp.plus.ImageSupplier[1]/plus:ImageSupplierName"]
                    == "ISIC Archive"
                )
                assert image_file.read_xmp()["Xmp.plus.ImageSupplierImageID"] == image.isic_id
                # see https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#lang-alt-value-type
                assert image_file.read_xmp()["Xmp.xmpRights.UsageTerms"] == {
                    'lang="x-default"': image.accession.copyright_license,
                }
                assert (
                    image_file.read_xmp()["Xmp.xmpRights.WebStatement"]
                    == LICENSE_URIS[image.accession.copyright_license]
                )
                assert (
                    image_file.read_xmp()["Xmp.plus.Licensor[1]/plus:LicensorURL"]
                    == "https://www.isic-archive.com"
                )
                assert (
                    image_file.read_xmp()["Xmp.plus.Licensor[1]/plus:LicensorName"]
                    == "ISIC Archive"
                )


@pytest.mark.django_db
def test_embed_iptc_metadata_idempotency(image_factory):
    image = image_factory(
        public=False,
        accession__attribution="attribution",
        accession__copyright_license="CC-0",
    )
    accession = image.accession
    attribution = accession.attribution
    copyright_license = accession.copyright_license

    with embed_iptc_metadata(
        accession.blob, attribution, copyright_license, image.isic_id
    ) as buffer:
        accession.blob = File(buffer)
        accession.save(update_fields=["blob"])

    with embed_iptc_metadata(accession.blob, attribution, copyright_license, image.isic_id) as _:
        pass
