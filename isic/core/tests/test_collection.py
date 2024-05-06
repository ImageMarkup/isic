from django.core.exceptions import ValidationError
from django.urls.base import reverse
import pytest

from isic.core.models.collection import Collection
from isic.core.services.collection.image import collection_move_images


@pytest.fixture()
def locked_collection(collection_factory, user):
    return collection_factory(locked=True, creator=user)


@pytest.mark.django_db()
def test_collection_form(authenticated_client, user):
    r = authenticated_client.post(
        reverse("core/collection-create"), {"name": "foo", "description": "bar", "public": False}
    )
    assert r.status_code == 302
    collection = Collection.objects.first()
    assert collection.creator == user
    assert collection.name == "foo"
    assert collection.description == "bar"
    assert collection.public is False


@pytest.mark.skip("Unimplemented")
def test_collection_locked_add_doi():
    # TODO: should be able to register a DOI on a locked collection
    pass


@pytest.fixture()
def collection_with_images(image_factory, collection_factory):
    private_coll = collection_factory(public=False)
    private_image = image_factory(public=False, accession__age=51)
    public_image = image_factory(public=True, accession__age=44)
    private_coll.images.add(private_image, public_image)
    return private_coll


@pytest.mark.django_db()
def test_collection_metadata_download(staff_client, collection_with_images, mocker):
    r = staff_client.get(
        reverse("core/collection-download-metadata", args=[collection_with_images.id])
    )
    assert r.status_code == 200

    output_csv = r.getvalue().decode("utf-8").splitlines()

    # writeheader and 2 writerow calls
    assert len(output_csv) == 3
    assert output_csv[0] == "isic_id,attribution,copyright_license,age_approx"

    for i, image in enumerate(collection_with_images.images.order_by("isic_id").all(), start=1):
        assert (
            output_csv[i]
            == f"{image.isic_id},{image.accession.cohort.attribution},{image.accession.copyright_license},{image.accession.age_approx}"  # noqa: E501
        )


@pytest.mark.django_db()
def test_collection_metadata_download_private_images(
    user, authenticated_client, collection_with_images, mocker
):
    # Add a share to the current user so that it can retrieve the CSV
    collection_with_images.shares.add(
        user, through_defaults={"creator": collection_with_images.creator}
    )

    r = authenticated_client.get(
        reverse("core/collection-download-metadata", args=[collection_with_images.id])
    )
    assert r.status_code == 200

    output_csv = r.getvalue().decode("utf-8").splitlines()

    # writeheader and 1 writerow calls, ignoring the private image because of permissions
    assert len(output_csv) == 2  # writeheader and 1 writerow call
    assert output_csv[0] == "isic_id,attribution,copyright_license,age_approx"

    image = collection_with_images.images.first()

    assert (
        output_csv[1]
        == f"{image.isic_id},{image.accession.cohort.attribution},{image.accession.copyright_license},{image.accession.age_approx}"  # noqa: E501
    )


@pytest.mark.django_db()
def test_collection_move_images(collection_factory, image_factory):
    collection_src, collection_dest = (
        collection_factory(public=True),
        collection_factory(public=True),
    )
    image = image_factory(public=True)
    collection_src.images.add(image)

    collection_move_images(src_collection=collection_src, dest_collection=collection_dest)

    assert collection_src.images.count() == 0
    assert collection_dest.images.count() == 1


@pytest.mark.django_db()
def test_collection_move_images_locked_collection(collection_factory, image_factory):
    collection_src, collection_dest = (
        collection_factory(public=True),
        collection_factory(public=True, locked=True),
    )
    image = image_factory(public=True)
    collection_src.images.add(image)

    with pytest.raises(ValidationError, match="locked collection"):
        collection_move_images(src_collection=collection_src, dest_collection=collection_dest)


@pytest.mark.django_db()
def test_collection_move_images_private_to_public(collection_factory, image_factory):
    collection_src, collection_dest = (
        collection_factory(public=False),
        collection_factory(public=True),
    )
    image = image_factory(public=False)
    collection_src.images.add(image)

    with pytest.raises(ValidationError, match="private images"):
        collection_move_images(src_collection=collection_src, dest_collection=collection_dest)


@pytest.mark.django_db()
def test_collection_move_images_already_exist_in_collection(collection_factory, image_factory):
    collection_src, collection_dest = (
        collection_factory(public=True),
        collection_factory(public=True),
    )
    image = image_factory(public=True)
    collection_src.images.add(image)
    collection_dest.images.add(image)

    collection_move_images(src_collection=collection_src, dest_collection=collection_dest)

    assert collection_src.images.count() == 0
    assert collection_dest.images.count() == 1
