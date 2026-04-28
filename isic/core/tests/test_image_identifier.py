from django.urls import reverse
import pytest

from isic.core.services.image import share_image


@pytest.mark.django_db
def test_resolve_isic_id(client, image_factory):
    image = image_factory(public=True)
    response = client.get(f"/images/{image.isic_id}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_resolve_girder_id(client, image_factory):
    image = image_factory(public=True, accession__girder_id="5436e3abbae478396759f0cf")
    response = client.get(f"/images/{image.accession.girder_id}/")
    assert response.status_code == 301
    assert response.url == reverse("core/image-detail", kwargs={"image_identifier": image.isic_id})


@pytest.mark.django_db
def test_resolve_pk(client, image_factory):
    image = image_factory(public=True)
    response = client.get(f"/images/{image.pk}/")
    assert response.status_code == 301
    assert response.url == reverse("core/image-detail", kwargs={"image_identifier": image.isic_id})


@pytest.mark.django_db
def test_resolve_pk_private_image_unauthenticated(client, image_factory):
    image = image_factory(public=False)
    response = client.get(f"/images/{image.pk}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_resolve_pk_private_image_authorized(client, user_factory, staff_user, image_factory):
    user = user_factory()
    image = image_factory(public=False)
    share_image(image=image, grantor=staff_user, grantee=user)
    client.force_login(user)
    response = client.get(f"/images/{image.pk}/")
    assert response.status_code == 301
    assert response.url == reverse("core/image-detail", kwargs={"image_identifier": image.isic_id})
