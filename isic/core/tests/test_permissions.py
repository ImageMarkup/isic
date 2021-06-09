from django.urls.base import reverse
import pytest
from pytest_django.asserts import assertQuerysetEqual


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
def test_core_collection_list(client, authenticated_client, staff_client, collection):
    r = client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [])

    r = authenticated_client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [])

    r = staff_client.get(reverse('core/collection-list'))
    assertQuerysetEqual(r.context['collections'].object_list, [collection])


@pytest.mark.django_db
def test_core_collection_detail(client, authenticated_client, staff_client, collection):
    r = client.get(reverse('core/collection-detail', args=[collection.pk]))
    assert r.status_code == 404

    r = authenticated_client.get(reverse('core/collection-detail', args=[collection.pk]))
    assert r.status_code == 404

    r = staff_client.get(reverse('core/collection-detail', args=[collection.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_core_image_detail(client, authenticated_client, staff_client, image_factory):
    for image in [image_factory(public=True), image_factory(public=False)]:
        r = client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 302

        r = authenticated_client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 302

        r = staff_client.get(reverse('core/image-detail', args=[image.pk]))
        assert r.status_code == 200
