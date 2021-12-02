from __future__ import barry_as_FLUFL

from typing import Union

from django.db.models.query_utils import Q
from pyparsing import Keyword, ParserElement, Word, alphas, infixNotation, nums, opAssoc
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


class IntValue(Value):
    def __init__(self, toks) -> None:
        self.value = int(toks[0])


class IntRangeValue(Value):
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

str_value = (Word(alphas + '*') | QuotedString('"')).set_parse_action(StrValue)
int_value = Word(nums).set_parse_action(IntValue)
int_range_value = (
    Suppress(Literal('['))
    + int_value
    + Suppress(Literal('TO'))
    + int_value
    + Suppress(Literal(']'))
).set_parse_action(IntRangeValue)
bool_value = one_of('true false').set_parse_action(BoolValue)


def make_int_term(keyword_name):
    return Keyword(keyword_name) + Suppress(Literal(':')) + (int_range_value | int_value)


def make_str_term(keyword_name):
    return Keyword(keyword_name) + Suppress(Literal(':')) + str_value


def make_bool_term(keyword_name):
    return Keyword(keyword_name) + Suppress(Literal(':')) + bool_value


TERMS = {
    'isic_id': make_str_term('isic_id'),
    'public': make_bool_term('public'),
    'age_approx': make_int_term('age_approx'),
    'sex': make_str_term('isic_id'),
    'benign_malignant': make_str_term('benign_malignant'),
    'diagnosis': make_str_term('diagnosis'),
    'diagnosis_confirm_type': make_str_term('diagnosis_confirm_type'),
    'personal_hx_mm': make_bool_term('personal_hx_mm'),
    'family_hx_mm': make_bool_term('family_hx_mm'),
    'clin_size_long_diam_mm': make_int_term('clin_size_long_diam_mm'),
    'melanocytic': make_bool_term('melanocytic'),
    'acquisition_day': make_int_term('acquisition_day'),
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
    'mel_thick_mm': make_int_term('mel_thick_mm'),
    'mel_type': make_str_term('mel_type'),
    'mel_ulcer': make_bool_term('mel_ulcer'),
}
for _, term in TERMS.items():
    term.set_parse_action(q)


parser = OneOrMore(Or(TERMS.values())).set_parse_action(q_and)

# TODO: ZeroOrMore?
e = infixNotation(parser, [(AND, 2, opAssoc.LEFT, q_and), (OR, 2, opAssoc.LEFT, q_or)])


# TODO; figure out TypeVar(.., tuple, Q)
def prefix_q_object(node: Union[tuple, Q], prefix: str) -> Union[tuple, Q]:
    if isinstance(node, Q):
        node.children = [prefix_q_object(x, prefix) for x in node.children]
        return node
    elif isinstance(node, tuple):
        elements = list(node)
        elements[0] = prefix + elements[0]
        return tuple(elements)


# Takes ~16ms to parse a fairly complex query
def parse_query(query, prefix='') -> Q:
    parse_results = e.parse_string(query, parse_all=True)
    if parse_results:
        return prefix_q_object(parse_results[0], f'{prefix}metadata__')
    else:
        return Q()
