from django.db.models.query_utils import Q
from pyparsing.exceptions import ParseException
import pytest

from isic.core.dsl import parse_query


@pytest.mark.parametrize(
    'query,filter_or_exception',
    [
        ['diagnosis:foobar', Q(metadata__diagnosis='foobar')],
        ['diagnosis:"foo bar"', Q(metadata__diagnosis='foo bar')],
        ['diagnosis:foo*', Q(metadata__diagnosis__startswith='foo')],
        ['diagnosis:*foo', Q(metadata__diagnosis__endswith='foo')],
        ['diagnosis:"foobar"', Q(metadata__diagnosis='foobar')],
        ['diagnosis:"foo*"', Q(metadata__diagnosis__startswith='foo')],
        ['diagnosis:"*foo"', Q(metadata__diagnosis__endswith='foo')],
        [
            'diagnosis:foobar AND diagnosis:foobaz',
            Q(metadata__diagnosis='foobar') & Q(metadata__diagnosis='foobaz'),
        ],
        [
            'diagnosis:foobar OR diagnosis:foobaz',
            Q(metadata__diagnosis='foobar') | Q(metadata__diagnosis='foobaz'),
        ],
        [
            'diagnosis:foobar OR (diagnosis:foobaz AND (diagnosis:foo* OR age_approx:50))',
            Q(metadata__diagnosis='foobar')
            | (
                Q(metadata__diagnosis='foobaz')
                & (Q(metadata__diagnosis__startswith='foo') | Q(metadata__age_approx=50))
            ),
        ],
        ['age_approx:50', Q(metadata__age_approx=50)],
        ['age_approx:[50 TO 70]', Q(metadata__age_approx__gte=50, metadata__age_approx__lte=70)],
        [
            'diagnosis:foo AND age_approx:[10 TO 12] AND diagnosis:bar AND diagnosis:baz',
            Q(metadata__diagnosis='foo')
            & Q(metadata__age_approx__gte=10)
            & Q(metadata__age_approx__lte=12)
            & Q(metadata__diagnosis='bar')
            & Q(metadata__diagnosis='baz'),
        ],
        ['diagnosis:foo randstring', ParseException],
        ['public:true', Q(metadata__public=True)],
        ['image_type:dermoscopic', Q(metadata__image_type='dermoscopic')],
        # test implicitly AND'ing terms
        [
            'public:true image_type:dermoscopic',
            Q(metadata__public=True) & Q(metadata__image_type='dermoscopic'),
        ],
    ],
)
def test_dsl_parser(query, filter_or_exception):
    if isinstance(filter_or_exception, Q):
        assert parse_query(query) == filter_or_exception
    elif isinstance(filter_or_exception, Exception):
        with pytest.assertRaises(filter_or_exception):
            parse_query(query)


def test_dsl_parser_prefixing():
    query = 'diagnosis:foo AND age_approx:[10 TO 12] AND diagnosis:bar AND diagnosis:baz'
    expected = (
        Q(foobar__metadata__diagnosis='foo')
        & Q(foobar__metadata__age_approx__gte=10)
        & Q(foobar__metadata__age_approx__lte=12)
        & Q(foobar__metadata__diagnosis='bar')
        & Q(foobar__metadata__diagnosis='baz')
    )
    assert parse_query(query, 'foobar__') == expected
