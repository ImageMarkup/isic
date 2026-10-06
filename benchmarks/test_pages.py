from urllib.parse import urlencode

from django.urls import reverse
import pytest

# (url name, the manifest key of its argument)
PUBLIC_PAGES = {
    "stats": ("stats/stats", None),
    "doi": ("core/doi-detail", "doi_slug"),
    "study": ("studies/study-detail", "public_study"),
}
STAFF_PAGES = {
    "cohort_list": ("ingest/cohort-list", None),
    "cohort_review": ("ingest/cohort-detail", "ingest_cohort"),
    "embargoed_dashboard": ("core/embargoed-dashboard", None),
    "admin_contributors": ("admin:ingest_contributor_changelist", None),
}


def _reverse(manifest: dict, name: str, key: str | None) -> str:
    return reverse(name, args=[manifest[key]] if key else [])


@pytest.mark.parametrize("page", PUBLIC_PAGES)
def test_public_page(benchmark, endpoint, manifest, page):
    benchmark(endpoint("anonymous", _reverse(manifest, *PUBLIC_PAGES[page])))


@pytest.mark.parametrize("page", STAFF_PAGES)
def test_staff_page(benchmark, endpoint, manifest, page):
    benchmark(endpoint("staff", _reverse(manifest, *STAFF_PAGES[page])))


@pytest.mark.parametrize("user", ["anonymous", "staff"])
@pytest.mark.parametrize("query", ["ISIC_00", "Benchmark", "Benign"])
def test_quickfind(benchmark_with_memory, endpoint, query, user):
    benchmark_with_memory(
        endpoint(user, f"{reverse('api:quickfind')}?{urlencode({'query': query})}")
    )
