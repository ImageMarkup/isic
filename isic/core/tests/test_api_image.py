import pytest


@pytest.mark.django_db
def test_core_api_image_ages_are_always_rounded(
    authenticated_api_client, staff_api_client, image_factory
):
    image = image_factory(accession__metadata={'age': 52}, public=True)

    for client in [authenticated_api_client, staff_api_client]:
        r = client.get('/api/v2/images/')
        assert r.status_code == 200, r.data
        assert r.data['count'] == 1
        assert r.data['results'][0]['metadata']['age_approx'] == 50

        r = client.get(f'/api/v2/images/{image.isic_id}/')
        assert r.status_code == 200, r.data
        assert r.data['metadata']['age_approx'] == 50
