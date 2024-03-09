from __future__ import barry_as_FLUFL

from dataclasses import dataclass
from typing import Any, Callable

from django.db.models.query_utils import Q
from isic_metadata import FIELD_REGISTRY
from pyparsing import Keyword, Optional, ParserElement, Word, alphas, infixNotation, nums, opAssoc
from pyparsing.common import pyparsing_common
from pyparsing.core import Literal, OneOrMore, Or, QuotedString, Suppress
from pyparsing.helpers import one_of
from pyparsing.results import ParseResults

ParserElement.enablePackrat()


@dataclass(frozen=True)
class SearchTermKey:
    field_lookup: str
    negated: bool = False


class Value:
    value: Any

    def to_q(self, key: SearchTermKey) -> Q:
        if self.value == "*":
            return Q(**{f"{key.field_lookup}__isnull": False}, _negated=key.negated)
        else:
            if key.negated:
                return ~Q(**{key.field_lookup: self.value}) | Q(
                    **{f"{key.field_lookup}__isnull": True}
                )
            return Q(**{key.field_lookup: self.value}, _negated=key.negated)

    def to_es(self, key: SearchTermKey) -> dict:
        if self.value == "*":
            term = {"exists": {"field": key.field_lookup}}
        else:
            term = {"term": {key.field_lookup: self.value}}

        if key.negated:
            return {"bool": {"must_not": term}}
        else:
            return term


class BoolValue(Value):
    def __init__(self, toks) -> None:
        if toks[0] == "*":
            self.value = "*"
        else:
            self.value = True if toks[0] == "true" else False


class StrValue(Value):
    def __init__(self, toks) -> None:
        self.value = toks[0]

    def to_q(self, key: SearchTermKey) -> Q:
        # Special casing for image type renaming, see
        # https://linear.app/isic/issue/ISIC-138#comment-93029f64
        # TODO: Remove this once better error messages are put in place.
        if key.field_lookup == "accession__image_type" and self.value == "clinical":
            self.value = "clinical: close-up"
        elif key.field_lookup == "accession__image_type" and self.value == "overview":
            self.value = "clinical: overview"

        # so asterisk is any present value
        if self.value == "*":
            return Q(**{f"{key.field_lookup}__isnull": False}, _negated=key.negated)
        if self.value.startswith("*"):
            if key.negated:
                return ~Q(**{f"{key.field_lookup}__startswith": self.value[1:]}) | Q(
                    **{f"{key.field_lookup}__isnull": True}
                )
            else:
                return Q(**{f"{key.field_lookup}__endswith": self.value[1:]}, _negated=key.negated)
        elif self.value.endswith("*"):
            if key.negated:
                return ~Q(**{f"{key.field_lookup}__startswith": self.value[:-1]}) | Q(
                    **{f"{key.field_lookup}__isnull": True}
                )
            else:
                return Q(
                    **{f"{key.field_lookup}__startswith": self.value[:-1]}, _negated=key.negated
                )
        else:
            return super().to_q(key)

    def to_es(self, key: SearchTermKey) -> dict:
        # Special casing for image type renaming, see
        # https://linear.app/isic/issue/ISIC-138#comment-93029f64
        # TODO: Remove this once better error messages are put in place.
        if key.field_lookup == "image_type" and self.value == "clinical":
            self.value = "clinical: close-up"
        elif key.field_lookup == "image_type" and self.value == "overview":
            self.value = "clinical: overview"

        if self.value == "*":
            term = {"exists": {"field": key.field_lookup}}
        elif self.value.startswith("*"):
            term = {"wildcard": {key.field_lookup: {"value": f"*{self.value[1:]}"}}}
        elif self.value.endswith("*"):
            term = {"wildcard": {key.field_lookup: {"value": f"{self.value[:-1]}*"}}}
        else:
            term = {"term": {key.field_lookup: self.value}}

        if key.negated:
            return {"bool": {"must_not": term}}
        else:
            return term


class NumberValue(Value):
    def __init__(self, toks) -> None:
        if toks[0] == "*":
            self.value = "*"
        else:
            self.value = toks[0]


class NumberRangeValue(Value):
    def __init__(self, toks) -> None:
        self.lower_lookup = "gte" if toks[0] == "[" else "gt"
        self.upper_lookup = "lte" if toks[-1] == "]" else "lt"
        self.value = (toks[1].value, toks[2].value)

    def to_q(self, key: SearchTermKey) -> Q:
        start_key, end_key = (
            f"{key.field_lookup}__{self.lower_lookup}",
            f"{key.field_lookup}__{self.upper_lookup}",
        )
        start_value, end_value = self.value
        if key.negated:
            return ~Q(**{start_key: start_value, end_key: end_value}) | Q(
                **{f"{key.field_lookup}__isnull": True}
            )
        else:
            return Q(**{start_key: start_value}, **{end_key: end_value}, _negated=key.negated)

    def to_es(self, key: SearchTermKey) -> dict:
        start_value, end_value = self.value
        term = {
            "range": {
                key.field_lookup: {
                    self.lower_lookup: start_value,
                    self.upper_lookup: end_value,
                }
            }
        }

        if key.negated:
            return {"bool": {"must_not": term}}
        else:
            return term


def es_query(s, loc, toks):
    key = toks[0]
    value = toks[1]
    return value.to_es(key)


def es_query_and(s, loc, toks):
    ret = {"bool": {"filter": []}}
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
        ret["bool"]["filter"].append(q)

    return ret


def es_query_or(s, loc, toks):
    ret = {"bool": {"should": []}}
    for tok in toks[0]:
        ret["bool"]["should"].append(tok)
    toks[0] = ret


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

# Note that the Lucene DSL treats a single asterisk as a replacement for whether
# the field exists and has a non null value.
# https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html#query-string-wildcard
EXISTS = Literal("*")

# asterisks for wildcard, _ for ISIC ID search, - for license types
str_value = (Word(alphas + nums + "*" + "_" + "-") | QuotedString('"')).add_parse_action(StrValue)
number_value = (pyparsing_common.number.copy() | EXISTS).add_parse_action(NumberValue)
concrete_number_value = pyparsing_common.number.copy().add_parse_action(NumberValue)
number_range_value = (
    one_of("[ {")
    + concrete_number_value
    + Suppress(Literal("TO"))
    + concrete_number_value
    + one_of("] }")
).add_parse_action(NumberRangeValue)
bool_value = one_of("true false *").add_parse_action(BoolValue)


def convert_term(s, loc, toks):
    negate = False

    if len(toks) == 2 and toks[0] == "-":
        negate = True
        toks = toks[1:]

    if len(toks) > 1:
        raise Exception("Something went wrong")

    if toks[0] == "public":
        return SearchTermKey(toks[0], negate)
    elif toks[0] == "isic_id":
        # isic_id can't be used with wildcards since it's a foreign key, so join the table and
        # refer to the __id.
        return SearchTermKey("isic__id", negate)
    elif toks[0] == "lesion_id":
        return SearchTermKey("accession__lesion__id", negate)
    elif toks[0] == "patient_id":
        return SearchTermKey("accession__patient__id", negate)
    elif toks[0] == "age_approx":
        return SearchTermKey("accession__age__approx", negate)
    elif toks[0] == "copyright_license":
        return SearchTermKey("accession__copyright_license", negate)
    else:
        return SearchTermKey(f"accession__{toks[0]}", negate)


def es_convert_term(s, loc, toks):
    negate = False

    if len(toks) == 2 and toks[0] == "-":
        negate = True
        toks = toks[1:]

    if len(toks) > 1:
        raise Exception("Something went wrong")

    return SearchTermKey(toks[0], negate)


def make_parser(
    element=q, conjunctive=q_and, disjunctive=q_or, term_converter: Callable = convert_term
) -> ParserElement:
    def make_term_keyword(name):
        term = Optional("-") + Keyword(name)
        if term_converter:
            term.add_parse_action(term_converter)
        return term

    def make_term(name, values):
        term = make_term_keyword(name)
        term = term + Suppress(Literal(":")) + values
        term.add_parse_action(element)
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
        # TODO: use one_of to get this validating maybe? it's hard to get this to work
        # with QuotedString
        "copyright_license": make_str_term("copyright_license"),
    }

    for key, definition in FIELD_REGISTRY.items():
        if definition.search:
            es_property_type = definition.search.es_property["type"]

            if es_property_type == "keyword":
                term = make_str_term(key)
            elif es_property_type == "boolean":
                term = make_bool_term(key)
            elif es_property_type in ["integer", "float"]:
                term = make_number_term(key)
            else:
                raise Exception("Found unknown es property type")

            TERMS[key] = term

    parser = OneOrMore(Or(TERMS.values())).add_parse_action(conjunctive)

    # TODO: ZeroOrMore?
    return infixNotation(
        parser, [(AND, 2, opAssoc.LEFT, conjunctive), (OR, 2, opAssoc.LEFT, disjunctive)]
    )


django_parser = make_parser()
es_parser = make_parser(es_query, es_query_and, es_query_or, es_convert_term)


# Takes ~16ms to parse a fairly complex query
def parse_query(parser, query) -> Q | dict | None:
    parse_results = parser.parse_string(query, parse_all=True)
    if parse_results:
        return parse_results[0]
