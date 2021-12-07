from django.db.models.query_utils import Q
from pyparsing.exceptions import ParseException
import pytest

from isic.core.dsl import parse_query


@pytest.mark.parametrize(
    'query,filter_or_exception',
    [
        ['diagnosis:foobar', Q(accession__metadata__diagnosis='foobar')],
        ['diagnosis:"foo bar"', Q(accession__metadata__diagnosis='foo bar')],
        ['diagnosis:foo*', Q(accession__metadata__diagnosis__startswith='foo')],
        ['diagnosis:*foo', Q(accession__metadata__diagnosis__endswith='foo')],
        ['diagnosis:"foobar"', Q(accession__metadata__diagnosis='foobar')],
        ['diagnosis:"foo*"', Q(accession__metadata__diagnosis__startswith='foo')],
        ['diagnosis:"*foo"', Q(accession__metadata__diagnosis__endswith='foo')],
        [
            'diagnosis:foobar AND diagnosis:foobaz',
            Q(accession__metadata__diagnosis='foobar') & Q(accession__metadata__diagnosis='foobaz'),
        ],
        [
            'diagnosis:foobar OR diagnosis:foobaz',
            Q(accession__metadata__diagnosis='foobar') | Q(accession__metadata__diagnosis='foobaz'),
        ],
        [
            'diagnosis:foobar OR (diagnosis:foobaz AND (diagnosis:foo* OR age_approx:50))',
            Q(accession__metadata__diagnosis='foobar')
            | (
                Q(accession__metadata__diagnosis='foobaz')
                & (
                    Q(accession__metadata__diagnosis__startswith='foo')
                    | Q(accession__metadata__age_approx=50)
                )
            ),
        ],
        ['age_approx:50', Q(accession__metadata__age__approx=50)],
        [
            'age_approx:[50 TO 70]',
            Q(accession__metadata__age__approx__gte=50, accession__metadata__age__approx__lte=70),
        ],
        [
            'diagnosis:foo AND age__approx:[10 TO 12] AND diagnosis:bar AND diagnosis:baz',
            Q(accession__metadata__diagnosis='foo')
            & Q(accession__metadata__age__approx__gte=10)
            & Q(accession__metadata__age__approx__lte=12)
            & Q(accession__metadata__diagnosis='bar')
            & Q(accession__metadata__diagnosis='baz'),
        ],
        ['diagnosis:foo randstring', ParseException],
        ['public:true', Q(public=True)],
        ['image_type:dermoscopic', Q(accession__metadata__image_type='dermoscopic')],
        # test implicitly AND'ing terms
        [
            'public:true image_type:dermoscopic',
            Q(public=True) & Q(accession__metadata__image_type='dermoscopic'),
        ],
    ],
)
def test_dsl_parser(query, filter_or_exception):
    if isinstance(filter_or_exception, Q):
        assert parse_query(query) == filter_or_exception
    elif isinstance(filter_or_exception, Exception):
        with pytest.assertRaises(filter_or_exception):
            parse_query(query)
