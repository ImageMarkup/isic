import pathlib

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.urls.base import reverse
import PIL
import PIL.ExifTags
import pytest

from isic.ingest.models.accession import Accession
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata
from isic.ingest.services.accession import accession_create, bulk_accession_relicense
from isic.ingest.utils.zip import Blob

data_dir = pathlib.Path(__file__).parent / "data"


@pytest.fixture
def user_with_cohort(user, cohort_factory):
    cohort = cohort_factory(contributor__creator=user)
    return user, cohort


@pytest.fixture
def jpg_blob():
    with pathlib.Path(data_dir / "ISIC_0000000.jpg").open("rb") as stream:
        yield Blob(
            name="ISIC_0000000.jpg",
            stream=stream,
            size=pathlib.Path(data_dir / "ISIC_0000000.jpg").stat().st_size,
        )


@pytest.fixture
def cc_by_accession_qs(accession_factory):
    accession = accession_factory(copyright_license="CC-BY")
    return Accession.objects.filter(id=accession.id)


@pytest.mark.django_db(transaction=True)
def test_accession_orients_images(user, cohort):
    name = "image_with_exif_including_orientation.jpg"
    path = data_dir / name

    with path.open("rb") as stream:
        original_blob = InMemoryUploadedFile(stream, None, name, None, path.stat().st_size, None)

        original_image = PIL.Image.open(original_blob)

        assert original_image._exif.get(PIL.ExifTags.Base.Make) == "Canon"
        assert original_image._exif.get(PIL.ExifTags.Base.Orientation) == 6  # 90 degrees clockwise

        accession = accession_create(
            creator=user,
            cohort=cohort,
            original_blob=original_blob,
            original_blob_name=name,
            original_blob_size=path.stat().st_size,
        )
        accession.refresh_from_db()

        processed_image = PIL.Image.open(accession.blob)

        # assert that all exif data is stripped but the orientation is applied
        assert processed_image._exif is None
        assert processed_image.height == original_image.width
        assert processed_image.width == original_image.height


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("blob_path", "blob_name", "mock_as_cog"),
    [
        # small color
        (pathlib.Path(data_dir / "ISIC_0000000.jpg"), "ISIC_0000000.jpg", False),
        # small grayscale
        (pathlib.Path(data_dir / "RCM_tile_with_exif.png"), "RCM_tile_with_exif.png", False),
        # big grayscale
        (pathlib.Path(data_dir / "RCM_tile_with_exif.png"), "RCM_tile_with_exif.png", True),
    ],
    ids=["small color", "small grayscale", "big grayscale"],
)
def test_accession_create_image_types(blob_path, blob_name, mock_as_cog, user, cohort, mocker):
    with blob_path.open("rb") as stream:
        original_blob = InMemoryUploadedFile(
            stream, None, blob_name, None, blob_path.stat().st_size, None
        )

        mocker.patch(
            "isic.ingest.services.accession.Accession.meets_cog_threshold",
            return_value=mock_as_cog,
        )

        accession = accession_create(
            creator=user,
            cohort=cohort,
            original_blob=original_blob,
            original_blob_name=blob_name,
            original_blob_size=blob_path.stat().st_size,
        )
        accession.refresh_from_db()

    assert accession.is_cog is mock_as_cog

    with accession.blob.open("rb") as blob:
        # This is exif metadata embedded in RCM_tile_with_exif.png that should be stripped
        assert b"foobar" not in blob.read()


@pytest.mark.django_db
def test_accession_generate_thumbnail(accession_factory):
    accession = accession_factory(thumbnail_256=None, thumbnail_256_size=None)

    accession.generate_thumbnail()

    with accession.thumbnail_256.open() as thumbnail_stream:
        thumbnail_content = thumbnail_stream.read()
        assert thumbnail_content.startswith(b"\xff\xd8")


@pytest.mark.django_db
def test_accession_without_zip_upload(user, jpg_blob, cohort):
    accession = Accession.from_blob(jpg_blob)
    accession.creator = user
    accession.cohort = cohort
    accession.copyright_license = cohort.default_copyright_license
    accession.attribution = cohort.default_attribution
    accession.unstructured_metadata = UnstructuredMetadata(accession=accession)
    accession.full_clean(validate_constraints=False)
    accession.save()


@pytest.mark.django_db
def test_accession_upload(authenticated_client, s3ff_field_value, user_with_cohort):
    _, cohort = user_with_cohort
    r = authenticated_client.post(
        reverse("upload/single-accession", args=[cohort.pk]),
        {"original_blob": s3ff_field_value, "age": "50"},
    )
    assert r.status_code == 302, r.data
    assert cohort.accessions.count() == 1
    assert cohort.accessions.first().metadata["age"] == 50


@pytest.mark.django_db
def test_accession_upload_duplicate_name(authenticated_client, s3ff_field_value, user_with_cohort):
    _, cohort = user_with_cohort
    r = authenticated_client.post(
        reverse("upload/single-accession", args=[cohort.pk]),
        {"original_blob": s3ff_field_value},
        follow=True,
    )
    assert r.status_code == 200, r.data
    assert cohort.accessions.count() == 1

    # try uploading the same file
    r = authenticated_client.post(
        reverse("upload/single-accession", args=[cohort.pk]),
        {"original_blob": s3ff_field_value},
    )
    assert r.status_code == 200, r.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_accession_upload_invalid_cohort(
    authenticated_client, s3ff_field_value, cohort_factory, user_factory
):
    # create a cohort owned by someone else to try to upload to
    cohort = cohort_factory(contributor__creator=user_factory())

    r = authenticated_client.get(reverse("upload/single-accession", args=[cohort.pk]))
    assert r.status_code == 403, r.data

    r = authenticated_client.post(
        reverse("upload/single-accession", args=[cohort.pk]),
        {"original_blob": s3ff_field_value},
    )
    assert r.status_code == 403, r.data


@pytest.mark.django_db
def test_accession_mutable_before_publish(user, accession_factory):
    accession = accession_factory()
    accession.update_metadata(user, {"foo": "bar"})
    accession.full_clean(validate_constraints=False)
    accession.save()


@pytest.mark.django_db
def test_accession_immutable_after_publish(user, image_factory):
    image = image_factory()

    with pytest.raises(ValidationError):
        image.accession.update_metadata(user, {"foo": "bar"})
        # image.accession.save()


@pytest.mark.django_db
def test_accession_relicense(cc_by_accession_qs):
    bulk_accession_relicense(accessions=cc_by_accession_qs, to_license="CC-0")
    assert cc_by_accession_qs.first().copyright_license == "CC-0"


@pytest.mark.django_db
def test_accession_relicense_more_restrictive(cc_by_accession_qs):
    with pytest.raises(ValidationError, match="more restrictive"):
        bulk_accession_relicense(accessions=cc_by_accession_qs, to_license="CC-BY-NC")


@pytest.mark.django_db
def test_accession_relicense_more_restrictive_ignore(cc_by_accession_qs):
    bulk_accession_relicense(
        accessions=cc_by_accession_qs, to_license="CC-BY-NC", allow_more_restrictive=True
    )


@pytest.mark.django_db
def test_accession_relicense_some_accessions_more_restrictive(
    cc_by_accession_qs, accession_factory
):
    # trying to relicense as CC-BY but an accession is CC-0
    accession = accession_factory(
        cohort=cc_by_accession_qs.first().cohort, copyright_license="CC-0"
    )
    accession.save()
    with pytest.raises(ValidationError, match="more restrictive"):
        bulk_accession_relicense(
            accessions=Accession.objects.filter(
                id__in=[cc_by_accession_qs.first().id, accession.id]
            ),
            to_license="CC-BY",
        )
