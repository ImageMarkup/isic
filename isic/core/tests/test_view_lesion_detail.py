from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.fixture()
def public_lesion(image_factory, lesion_factory):
    lesion = lesion_factory()
    image_factory(accession__lesion=lesion, public=True)
    return lesion


@pytest.fixture()
def partially_public_lesion(image_factory, lesion_factory):
    lesion = lesion_factory()
    image_factory(accession__lesion=lesion, public=True)
    image_factory(accession__lesion=lesion, public=False)
    return lesion


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "lesion_", "can_see"),
    [
        (lf("client"), lf("public_lesion"), True),
        (lf("client"), lf("partially_public_lesion"), False),
        (lf("authenticated_client"), lf("public_lesion"), True),
        (lf("authenticated_client"), lf("partially_public_lesion"), False),
        (lf("staff_client"), lf("public_lesion"), True),
        (lf("staff_client"), lf("partially_public_lesion"), True),
    ],
)
def test_core_lesion_detail(client_, lesion_, can_see):
    r = client_.get(reverse("core/lesion-detail", args=[lesion_.pk]))
    assert r.status_code == 200 if can_see else 404
