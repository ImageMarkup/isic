from __future__ import barry_as_FLUFL

from django.db.models.query_utils import Q
from isic_metadata import FIELD_REGISTRY
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
        self.value = True if toks[0] == "true" else False


class StrValue(Value):
    def __init__(self, toks) -> None:
        self.value = toks[0]

    def to_q(self, key):
        if self.value.startswith("*"):
            return Q(**{f"{key}__endswith": self.value[1:]})
        elif self.value.endswith("*"):
            return Q(**{f"{key}__startswith": self.value[:-1]})
        else:
            return super().to_q(key)


class NumberValue(Value):
    def __init__(self, toks) -> None:
        self.value = toks[0]


class NumberRangeValue(Value):
    def __init__(self, toks) -> None:
        self.lower_lookup = "gte" if toks[0] == "[" else "gt"
        self.upper_lookup = "lte" if toks[-1] == "]" else "lt"
        self.value = (toks[1].value, toks[2].value)

    def to_q(self, key):
        start_key, end_key = f"{key}__{self.lower_lookup}", f"{key}__{self.upper_lookup}"
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
        raise Exception("Something went wrong")

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
AND = Suppress(Keyword("AND"))
OR = Suppress(Keyword("OR"))

# asterisks for wildcard, _ for ISIC ID search, - for license types
str_value = (Word(alphas + nums + "*" + "_" + "-") | QuotedString('"')).add_parse_action(StrValue)
number_value = pyparsing_common.number.add_parse_action(NumberValue)
number_range_value = (
    one_of("[ {") + number_value + Suppress(Literal("TO")) + number_value + one_of("] }")
).add_parse_action(NumberRangeValue)
bool_value = one_of("true false").add_parse_action(BoolValue)


def convert_term(s, loc, toks):
    if toks[0] in ["isic_id", "public"]:
        return toks[0]
    elif toks[0] == "age_approx":
        return "accession__metadata__age__approx"
    elif toks[0] == "copyright_license":
        return "accession__copyright_license"
    else:
        return f"accession__metadata__{toks[0]}"


def make_term_keyword(name):
    return Keyword(name).add_parse_action(convert_term)


def make_term(name, values):
    term = make_term_keyword(name)
    term = term + Suppress(Literal(":")) + values
    term.add_parse_action(q)
    return term


def make_number_term(keyword_name):
    return make_term(keyword_name, number_range_value | number_value)


def make_str_term(keyword_name):
    return make_term(keyword_name, str_value)


def make_bool_term(keyword_name):
    return make_term(keyword_name, bool_value)


# First setup reserved (special) search terms
TERMS = {
    "isic_id": make_str_term("isic_id"),
    "public": make_bool_term("public"),
    "age_approx": make_number_term("age_approx"),
    # TODO: use one_of to get this validating maybe? it's hard to get this to work with QuotedString
    "copyright_license": make_str_term("copyright_license"),
}

for key, definition in FIELD_REGISTRY.items():
    if definition.get("search"):
        es_property_type = definition["search"]["es_property"]["type"]

        if es_property_type == "keyword":
            term = make_str_term(key)
        elif es_property_type == "boolean":
            term = make_bool_term(key)
        elif es_property_type in ["integer", "float"]:
            term = make_number_term(key)
        else:
            raise Exception("Found unknown es property type")

        TERMS[key] = term

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
