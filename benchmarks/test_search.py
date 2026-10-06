from django.contrib.auth.models import AnonymousUser, User
import pytest

from isic.core.dsl import django_parser, es_parser, parse_query
from isic.core.search import build_elasticsearch_query

QUERIES = {
    "simple": "diagnosis_1:Benign",
    "boolean": "diagnosis_1:Malignant AND image_type:dermoscopic AND -sex:male",
    "nested": (
        'diagnosis_3:"Melanoma, NOS" OR (image_type:dermoscopic AND '
        "(age_approx:[30 TO 50] OR anatom_site_1:Trunk OR diagnosis_2:*proliferations))"
    ),
}
PARSERS = {"django": django_parser, "elasticsearch": es_parser}


@pytest.mark.parametrize("parser", PARSERS)
@pytest.mark.parametrize("query", QUERIES)
def test_parse_query(benchmark, query, parser):
    """Parse the search DSL without parse_query's cache."""
    benchmark(parse_query.__wrapped__, PARSERS[parser], QUERIES[query])


@pytest.mark.parametrize("collections", ["none", "large"])
@pytest.mark.parametrize("user", ["anonymous", "shares", "owner", "staff"])
def test_build_elasticsearch_query(benchmark, manifest, user, collections):
    user = AnonymousUser() if user == "anonymous" else User.objects.get(pk=manifest["users"][user])
    collection_ids = [manifest["collections"]["large"]] if collections == "large" else None
    benchmark(build_elasticsearch_query, {}, user, collection_ids)
