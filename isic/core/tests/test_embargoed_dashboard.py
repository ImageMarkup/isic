from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_embargoed_dashboard_shows_embargoed_images(staff_client, image_factory):
    embargoed_image = image_factory(public=False)

    r = staff_client.get(reverse("core/embargoed-dashboard"))
    assert r.status_code == 200

    cohort_pks = [cohort.pk for cohort in r.context["cohorts_with_embargoed"]]
    assert embargoed_image.accession.cohort.pk == cohort_pks[0]

    assert r.context["total_embargoed"] == 1
