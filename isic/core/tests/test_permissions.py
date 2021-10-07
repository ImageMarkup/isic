from django.urls.base import reverse
import pytest
from pytest_django.asserts import assertQuerysetEqual


@pytest.fixture
def private_collection(collection_factory):
    collection = collection_factory(public=False)
    return collection


@pytest.fixture
def public_collection(collection_factory):
    collection = collection_factory(public=True)
    return collection


@pytest.mark.django_db
def test_core_stats(client):
    r = client.get(reverse('core/stats'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_core_api_stats(client):
    r = client.get(reverse('core/api/stats'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_core_staff_list(client, authenticated_client, staff_client):
    r = client.get(reverse('core/staff-list'))
    assert r.status_code == 404

    r = authenticated_client.get(reverse('core/staff-list'))
    assert r.status_code == 404

    r = staff_client.get(reverse('core/staff-list'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_core_collection_list(client, authenticated_client, staff_client, private_collection):
    r = client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [])

    r = authenticated_client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [])

    r = staff_client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [private_collection])


@pytest.mark.django_db
def test_core_collection_detail(client, authenticated_client, staff_client, private_collection):
    r = client.get(reverse('core/collection-detail', args=[private_collection.pk]))
    assert r.status_code == 404

    r = authenticated_client.get(reverse('core/collection-detail', args=[private_collection.pk]))
    assert r.status_code == 404

    r = staff_client.get(reverse('core/collection-detail', args=[private_collection.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_core_collection_detail_filters_contributors(
    client, authenticated_client, staff_client, public_collection, image_factory
):
    image = image_factory(public=True)
    public_collection.images.add(image)
    r = client.get(reverse('core/collection-detail', args=[public_collection.pk]))
    assert r.status_code == 200
    assert list(r.context['contributors']) == []

    r = authenticated_client.get(reverse('core/collection-detail', args=[public_collection.pk]))
    assert r.status_code == 200
    assert list(r.context['contributors']) == []

    r = staff_client.get(reverse('core/collection-detail', args=[public_collection.pk]))
    assert r.status_code == 200
    assert list(r.context['contributors']) == [image.accession.upload.cohort.contributor]


@pytest.mark.django_db
def test_core_image_detail(client, authenticated_client, staff_client, image_factory):
    for image in [image_factory(public=True), image_factory(public=False)]:
        r = client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 302

        r = authenticated_client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 302

        r = staff_client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 200
