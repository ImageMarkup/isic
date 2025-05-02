from django.db.models.query_utils import Q
from pyparsing.exceptions import ParseException
import pytest

from isic.core.dsl import django_parser, es_parser, parse_query

# test null problem


@pytest.mark.parametrize(
    ("query", "filter_or_exception"),
    [
        # test isic_id especially due to the weirdness of the foreign key
        ("isic_id:ISIC_123*", Q(isic__id__startswith="ISIC_123")),
        # test negation and present/missing values
        ("-isic_id:*", ~Q(isic__id__isnull=False)),
        ("-lesion_id:*", ~Q(accession__lesion__id__isnull=False)),
        ("-mel_thick_mm:*", ~Q(accession__mel_thick_mm__isnull=False)),
        ("age_approx:[50 TO *]", ParseException),
        ("-melanocytic:*", ~Q(accession__melanocytic__isnull=False)),
        ("melanocytic:*", Q(accession__melanocytic__isnull=False)),
        (
            "-age_approx:50",
            ~Q(accession__age__approx=50) | Q(accession__age__approx__isnull=True),
        ),
        (
            "-age_approx:[50 TO 70]",
            ~Q(accession__age__approx__gte=50, accession__age__approx__lte=70)
            | Q(accession__age__approx__isnull=True),
        ),
        ("isic_id:*123", Q(isic__id__endswith="123")),
        ("lesion_id:IL_123*", Q(accession__lesion__id__startswith="IL_123")),
        ("lesion_id:*123", Q(accession__lesion__id__endswith="123")),
        ("patient_id:IP_123*", Q(accession__patient__id__startswith="IP_123")),
        ("patient_id:*123", Q(accession__patient__id__endswith="123")),
        ("rcm_case_id:123*", Q(accession__rcm_case__id__startswith="123")),
        ("rcm_case_id:*123", Q(accession__rcm_case__id__endswith="123")),
        ('copyright_license:"CC-0"', Q(accession__copyright_license="CC-0")),
        ("age_approx:50", Q(accession__age__approx=50)),
        (
            "age_approx:[50 TO 70]",
            Q(accession__age__approx__gte=50, accession__age__approx__lte=70),
        ),
        (
            "age_approx:{50 TO 70}",
            Q(accession__age__approx__gt=50, accession__age__approx__lt=70),
        ),
        (
            "age_approx:[50 TO 70}",
            Q(accession__age__approx__gte=50, accession__age__approx__lt=70),
        ),
        (
            "mel_thick_mm:[0 TO 0.5]",
            Q(accession__mel_thick_mm__gte=0, accession__mel_thick_mm__lte=0.5),
        ),
        ("diagnosis_1:foo randstring", ParseException),
        ("public:true", Q(public=True)),
        ("image_type:dermoscopic", Q(accession__image_type="dermoscopic")),
        # test implicitly AND'ing terms
        (
            "public:true image_type:dermoscopic",
            Q(public=True) & Q(accession__image_type="dermoscopic"),
        ),
    ],
)
def test_dsl_django_parser(query, filter_or_exception):
    if isinstance(filter_or_exception, Q):
        assert parse_query(django_parser, query) == filter_or_exception
    else:
        with pytest.raises(filter_or_exception):
            parse_query(django_parser, query)


@pytest.mark.parametrize(
    ("query", "filter"),
    [
        (
            "isic_id:ISIC_123*",
            {"bool": {"filter": [{"wildcard": {"isic_id": {"value": "ISIC_123*"}}}]}},
        ),
        (
            "-isic_id:*",
            {"bool": {"filter": [{"bool": {"must_not": {"exists": {"field": "isic_id"}}}}]}},
        ),
        (
            "diagnosis_1:foobar OR (diagnosis_1:foobaz AND (diagnosis_1:foo* OR age_approx:50))",
            {
                "bool": {
                    "should": [
                        {"bool": {"filter": [{"term": {"diagnosis_1": "foobar"}}]}},
                        {
                            "bool": {
                                "filter": [
                                    {"bool": {"filter": [{"term": {"diagnosis_1": "foobaz"}}]}},
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "bool": {
                                                        "filter": [
                                                            {
                                                                "wildcard": {
                                                                    "diagnosis_1": {"value": "foo*"}
                                                                }
                                                            }
                                                        ]
                                                    }
                                                },
                                                {
                                                    "bool": {
                                                        "filter": [{"term": {"age_approx": 50}}]
                                                    }
                                                },
                                            ]
                                        }
                                    },
                                ]
                            }
                        },
                    ]
                }
            },
        ),
    ],
)
def test_dsl_es_parser(query, filter):
    assert parse_query(es_parser, query) == filter


@pytest.mark.parametrize(
    ("query", "filter"),
    [
        ("image_type:clinical", Q(accession__image_type="clinical: close-up")),
        ("image_type:overview", Q(accession__image_type="clinical: overview")),
    ],
)
def test_dsl_image_type_backwards_compatible(query, filter):
    assert parse_query(django_parser, query) == filter
