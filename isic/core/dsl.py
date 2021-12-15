from __future__ import barry_as_FLUFL

from django.db.models.query_utils import Q
from pyparsing import Keyword, ParserElement, Word, alphas, infixNotation, nums, opAssoc
from pyparsing.common import pyparsing_common
from pyparsing.core import Literal, OneOrMore, Or, QuotedString, Suppress
from pyparsing.helpers import one_of
from pyparsing.results import ParseResults

ParserElement.enablePackrat()


class Value:
    def to_q(self, key):
        return Q(**{key: self.value})


class BoolValue(Value):
    def __init__(self, toks) -> None:
        self.value = True if toks[0] == 'true' else False


class StrValue(Value):
    def __init__(self, toks) -> None:
        self.value = toks[0]

    def to_q(self, key):
        if self.value.startswith('*'):
            return Q(**{f'{key}__endswith': self.value[1:]})
        elif self.value.endswith('*'):
            return Q(**{f'{key}__startswith': self.value[:-1]})
        else:
            return super().to_q(key)


class NumberValue(Value):
    def __init__(self, toks) -> None:
        self.value = toks[0]


class NumberRangeValue(Value):
    def __init__(self, toks) -> None:
        self.value = (toks[0].value, toks[1].value)

    def to_q(self, key):
        start_key, end_key = f'{key}__gte', f'{key}__lte'
        start_value, end_value = self.value
        return Q(**{start_key: start_value}, **{end_key: end_value})


def q(s, loc, toks):
    key = toks[0]
    value = toks[1]
    return value.to_q(key)


def q_and(s, loc, toks):
    ret = Q()
    if isinstance(toks, ParseResults):
        # Explicit ANDs come in as parse results
        q_objects = toks.asList()
    elif isinstance(toks[0], Q):
        # Single search queries come in as a single Q object
        q_objects = [toks[0]]
    else:
        raise Exception('Something went wrong')

    # Results can be nested one level
    if isinstance(q_objects, list) and isinstance(q_objects[0], list):
        q_objects = q_objects[0]

    for q in q_objects:
        ret &= q

    return ret


def q_or(s, loc, toks):
    ret = Q()
    for tok in toks[0]:
        ret |= tok
    toks[0] = ret


# Lucene DSL only supports uppercase AND/OR/TO
AND = Suppress(Keyword('AND'))
OR = Suppress(Keyword('OR'))

# asterisks for wildcard, _ for ISIC ID search
str_value = (Word(alphas + nums + '*' + '_') | QuotedString('"')).add_parse_action(StrValue)
number_value = pyparsing_common.fnumber.add_parse_action(NumberValue)
number_range_value = (
    Suppress(Literal('['))
    + number_value
    + Suppress(Literal('TO'))
    + number_value
    + Suppress(Literal(']'))
).add_parse_action(NumberRangeValue)
bool_value = one_of('true false').add_parse_action(BoolValue)


def convert_term(s, loc, toks):
    if toks[0] in ['isic_id', 'public']:
        return toks[0]
    elif toks[0] == 'age_approx':
        return 'accession__metadata__age__approx'
    else:
        return f'accession__metadata__{toks[0]}'


def make_term_keyword(name):
    return Keyword(name).add_parse_action(convert_term)


def make_term(name, values):
    term = make_term_keyword(name)
    term = term + Suppress(Literal(':')) + values
    term.add_parse_action(q)
    return term


def make_number_term(keyword_name):
    return make_term(keyword_name, number_range_value | number_value)


def make_str_term(keyword_name):
    return make_term(keyword_name, str_value)


def make_bool_term(keyword_name):
    return make_term(keyword_name, bool_value)


TERMS = {
    'isic_id': make_str_term('isic_id'),
    'public': make_bool_term('public'),
    'age_approx': make_number_term('age_approx'),
    'sex': make_str_term('sex'),
    'benign_malignant': make_str_term('benign_malignant'),
    'diagnosis': make_str_term('diagnosis'),
    'diagnosis_confirm_type': make_str_term('diagnosis_confirm_type'),
    'personal_hx_mm': make_bool_term('personal_hx_mm'),
    'family_hx_mm': make_bool_term('family_hx_mm'),
    'clin_size_long_diam_mm': make_number_term('clin_size_long_diam_mm'),
    'melanocytic': make_bool_term('melanocytic'),
    'acquisition_day': make_number_term('acquisition_day'),
    'marker_pen': make_bool_term('marker_pen'),
    'hairy': make_bool_term('hairy'),
    'blurry': make_bool_term('blurry'),
    'nevus_type': make_str_term('nevus_type'),
    'image_type': make_str_term('image_type'),
    'dermoscopic_type': make_str_term('dermoscopic_type'),
    'anatom_site_general': make_str_term('anatom_site_general'),
    'color_tint': make_str_term('color_tint'),
    'mel_class': make_str_term('mel_class'),
    'mel_mitotic_index': make_str_term('mel_mitotic_index'),
    'mel_thick_mm': make_number_term('mel_thick_mm'),
    'mel_type': make_str_term('mel_type'),
    'mel_ulcer': make_bool_term('mel_ulcer'),
}


parser = OneOrMore(Or(TERMS.values())).add_parse_action(q_and)

# TODO: ZeroOrMore?
e = infixNotation(parser, [(AND, 2, opAssoc.LEFT, q_and), (OR, 2, opAssoc.LEFT, q_or)])


# Takes ~16ms to parse a fairly complex query
def parse_query(query) -> Q:
    parse_results = e.parse_string(query, parse_all=True)
    if parse_results:
        return parse_results[0]
    else:
        return Q()
