from django.urls.base import reverse
import pytest

from isic.core.models.collection import Collection


@pytest.fixture
def locked_collection(collection_factory, user):
    return collection_factory(locked=True, creator=user)


@pytest.mark.django_db
def test_collection_form(authenticated_client, user):
    r = authenticated_client.post(
        reverse('core/collection-create'), {'name': 'foo', 'description': 'bar', 'public': False}
    )
    assert r.status_code == 302
    collection = Collection.objects.first()
    assert collection.creator == user
    assert collection.name == 'foo'
    assert collection.description == 'bar'
    assert collection.public is False


@pytest.mark.skip('Unimplemented')
def test_collection_locked_add_doi():
    # TODO: should be able to register a DOI on a locked collection
    pass


@pytest.fixture
def collection_with_images(image_factory, collection_factory):
    private_coll = collection_factory(public=False)
    private_image = image_factory(public=False, accession__metadata={'age': 51})
    public_image = image_factory(public=True, accession__metadata={'age': 44})
    private_coll.images.add(private_image, public_image)
    yield private_coll


@pytest.mark.django_db
def test_collection_metadata_download(staff_client, collection_with_images, mocker):
    mock_writer = mocker.MagicMock()
    mocker.patch('isic.core.views.collections.csv.DictWriter', return_value=mock_writer)

    r = staff_client.get(
        reverse('core/collection-download-metadata', args=[collection_with_images.id])
    )
    assert r.status_code == 200

    assert len(mock_writer.method_calls) == 3  # writeheader and 2 writerow calls

    first_image = collection_with_images.images.order_by('isic_id').first()
    assert mock_writer.method_calls[1].args[0] == {
        'isic_id': first_image.isic_id,
        'attribution': first_image.accession.cohort.attribution,
        'copyright_license': first_image.accession.cohort.copyright_license,
        'age_approx': first_image.accession.age_approx,
    }

    second_image = collection_with_images.images.order_by('isic_id').last()
    assert mock_writer.method_calls[2].args[0] == {
        'isic_id': second_image.isic_id,
        'attribution': second_image.accession.cohort.attribution,
        'copyright_license': second_image.accession.cohort.copyright_license,
        'age_approx': second_image.accession.age_approx,
    }


@pytest.mark.django_db
def test_collection_metadata_download_private_images(
    user, authenticated_client, collection_with_images, mocker
):
    # Add a share to the current user so that it can retrieve the CSV
    collection_with_images.shares.add(
        user, through_defaults={'creator': collection_with_images.creator}
    )

    mock_writer = mocker.MagicMock()
    mocker.patch('isic.core.views.collections.csv.DictWriter', return_value=mock_writer)

    r = authenticated_client.get(
        reverse('core/collection-download-metadata', args=[collection_with_images.id])
    )
    assert r.status_code == 200

    # writeheader and 1 writerow calls, ignoring the private image because of permissions
    assert len(mock_writer.method_calls) == 2

    image = collection_with_images.images.first()
    assert mock_writer.method_calls[1].args[0] == {
        'isic_id': image.isic_id,
        'attribution': image.accession.cohort.attribution,
        'copyright_license': image.accession.cohort.copyright_license,
        'age_approx': image.accession.age_approx,
    }
