import pytest
from pytest_lazyfixture import lazy_fixture


@pytest.mark.django_db
def test_api_lesion(authenticated_client, lesion_factory, image_factory):
    lesion = lesion_factory()
    image_factory(accession__lesion=lesion)

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()


@pytest.mark.django_db
def test_api_lesion_ignores_imageless_lesions(authenticated_client, lesion_factory, user):
    # give access to the lesion to ensure this isn't passing due to lack of permissions
    lesion_factory(cohort__contributor__owners=[user])

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
    assert len(resp.json()["results"]) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ["client_", "image_public_states", "expected_lesion_count"],
    [
        [lazy_fixture("client"), [True, True], 1],
        [lazy_fixture("client"), [True, False], 0],
        [lazy_fixture("client"), [False, False], 0],
        [lazy_fixture("authenticated_client"), [True, True], 1],
        [lazy_fixture("authenticated_client"), [True, False], 0],
        [lazy_fixture("authenticated_client"), [False, False], 0],
        [lazy_fixture("staff_client"), [True, True], 1],
        [lazy_fixture("staff_client"), [True, False], 1],
        [lazy_fixture("staff_client"), [False, False], 1],
    ],
)
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
def test_api_lesion_permissions_contributor(
    authenticated_client, lesion_factory, image_factory, contributor
):
    lesion = lesion_factory()
    image_factory(
        accession__lesion=lesion, accession__cohort__contributor=contributor, public=False
    )

    resp = authenticated_client.get("/api/v2/lesions/")
    assert resp.status_code == 200, resp.json()
