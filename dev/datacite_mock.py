# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "flask>=3.1",
# ]
# ///
"""
A stand-in for the parts of the DataCite REST API that isic uses.

Behavior was recorded from api.test.datacite.org, quirks included: a POST with bad credentials
returns 404, a PUT to an unknown DOI creates it, the style parameter of a text/x-bibliography
Accept header is ignored in favor of the ?style= query parameter, and
chicago-fullnote-bibliography renders as APA, like any style DataCite doesn't know. Citations
are modeled on Dataset records, the only resource type isic registers.

State is kept in memory. POST /_mock/reset clears it; that endpoint is not part of DataCite.

    uv run dev/datacite_mock.py --port 8001
    DJANGO_ISIC_DATACITE_API_URL=http://mock.isic:password@localhost:8001
"""

from __future__ import annotations

import argparse
import base64
import copy
from datetime import UTC, datetime
import functools
from http import HTTPStatus
import json
import re
import secrets
import threading
from typing import TYPE_CHECKING, NamedTuple
from xml.sax.saxutils import escape

from flask import Flask, Response, current_app, request

if TYPE_CHECKING:
    from collections.abc import Callable

JSON_TYPE = "application/json; charset=utf-8"
SCHEMA_ORG_TYPE = "application/vnd.schemaorg.ld+json"
BIBLIOGRAPHY_TYPE = "text/x-bibliography"
DATACITE_XML_TYPE = "application/vnd.datacite.datacite+xml"

NOT_FOUND = "The resource you are looking for doesn't exist."
FORBIDDEN = "You are not authorized to access this resource."
KERNEL_NS = "{http://datacite.org/schema/kernel-4}"
XML_ATTRIBUTE_ENTITIES = {'"': "&quot;"}

# in the order DataCite serializes them
METADATA_FIELDS = [
    "identifiers",
    "alternateIdentifiers",
    "creators",
    "titles",
    "publisher",
    "container",
    "publicationYear",
    "subjects",
    "contributors",
    "dates",
    "language",
    "types",
    "relatedIdentifiers",
    "relatedItems",
    "sizes",
    "formats",
    "version",
    "rightsList",
    "descriptions",
    "geoLocations",
    "fundingReferences",
]
SCALAR_FIELDS = {"publisher", "publicationYear", "language", "version"}
EMPTY_RELATIONSHIPS = ["references", "citations", "parts", "partOf", "versions", "versionOf"]

RESOURCE_TYPES = {
    "Dataset": {"schemaOrg": "Dataset", "citeproc": "dataset", "bibtex": "misc", "ris": "DATA"},
    "Software": {
        "schemaOrg": "SoftwareSourceCode",
        "citeproc": "article",
        "bibtex": "misc",
        "ris": "COMP",
    },
}
APA_TYPE_LABELS = {"Dataset": "Dataset", "Software": "Computer software"}

# DataCite replaces rights that name one of these by SPDX ID or name
SPDX_LICENSES = {
    "cc0-1.0": ("Creative Commons Zero v1.0 Universal", "publicdomain/zero/1.0"),
    "cc-by-4.0": ("Creative Commons Attribution 4.0 International", "licenses/by/4.0"),
    "cc-by-nc-4.0": (
        "Creative Commons Attribution Non Commercial 4.0 International",
        "licenses/by-nc/4.0",
    ),
    "cc-by-sa-4.0": (
        "Creative Commons Attribution Share Alike 4.0 International",
        "licenses/by-sa/4.0",
    ),
    "cc-by-nd-4.0": (
        "Creative Commons Attribution No Derivatives 4.0 International",
        "licenses/by-nd/4.0",
    ),
    "cc-by-nc-sa-4.0": (
        "Creative Commons Attribution Non Commercial Share Alike 4.0 International",
        "licenses/by-nc-sa/4.0",
    ),
    "cc-by-nc-nd-4.0": (
        "Creative Commons Attribution Non Commercial No Derivatives 4.0 International",
        "licenses/by-nc-nd/4.0",
    ),
}

# citeproc-ruby's English stop words, as observed through MLA title casing
STOP_WORDS = set(
    """
    about above across afore after against along alongside amid amidst among amongst anenst
    apropos apud around as aside astride at athwart atop barring before behind below beneath
    beside besides between beyond but by circa despite down during except for forenenst from
    given in inside into lest like modulo near next notwithstanding of off on onto out over per
    plus pro qua sans since than through thru throughout thruout till to toward towards under
    underneath until unto up upon versus vs via with within without or so and nor an the
    """.split()  # noqa: SIM905
)

BASE32_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, errors: list[dict], content_type: str = JSON_TYPE):
        self.status = status
        self.errors = errors
        self.content_type = content_type


def _status_error(status: HTTPStatus, title: str, content_type: str = JSON_TYPE) -> ApiError:
    return ApiError(status, [{"status": str(status.value), "title": title}], content_type)


def _field_error(source: str, title: str, doi: str) -> ApiError:
    return ApiError(
        HTTPStatus.UNPROCESSABLE_ENTITY, [{"source": source, "title": title, "uid": doi}]
    )


def _timestamp(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z") if value else None


def _generate_suffix() -> str:
    """Generate a suffix like DataCite's: 6 base32 characters and a mod 97 checksum."""
    number = secrets.randbits(30)
    encoded, remaining = "", number
    for _ in range(6):
        remaining, digit = divmod(remaining, 32)
        encoded = BASE32_ALPHABET[digit] + encoded
    suffix = f"{encoded}{98 - (number * 100) % 97:02}"
    return f"{suffix[:4]}-{suffix[4:]}"


def _mysql_json_order(value):
    if isinstance(value, dict):
        return {
            key: _mysql_json_order(value[key])
            for key in sorted(value, key=lambda k: (len(k.encode()), k.encode()))
        }
    if isinstance(value, list):
        return [_mysql_json_order(item) for item in value]
    return value


def _compact(mapping: dict) -> dict:
    return {key: value for key, value in mapping.items() if value is not None}


def _normalize_rights(rights: dict) -> dict:
    identifier = (rights.get("rightsIdentifier") or "").lower()
    normalized = {
        "rights": rights.get("rights"),
        "rightsUri": rights.get("rightsUri"),
        "rightsIdentifier": identifier or None,
        "rightsIdentifierScheme": rights.get("rightsIdentifierScheme"),
        "schemeUri": rights.get("schemeUri"),
        "lang": rights.get("lang"),
    }
    for license_id, (name, path) in SPDX_LICENSES.items():
        if normalized["rights"] == name or identifier == license_id:
            normalized |= {
                "rights": name,
                "rightsUri": f"https://creativecommons.org/{path}/legalcode",
                "rightsIdentifier": license_id,
                "rightsIdentifierScheme": "SPDX",
                "schemeUri": "https://spdx.org/licenses/",
            }
            break
    return _compact(normalized)


def _normalize_types(types: dict | None) -> dict:
    general = (types or {}).get("resourceTypeGeneral")
    return {**RESOURCE_TYPES.get(general, {}), **types} if general else {}


NORMALIZERS = {
    "identifiers": lambda value: [i for i in value or [] if i.get("identifierType") != "DOI"],
    "creators": lambda value: [
        {
            **creator,
            "affiliation": creator.get("affiliation", []),
            "nameIdentifiers": creator.get("nameIdentifiers", []),
        }
        for creator in value or []
    ],
    "rightsList": lambda value: [_normalize_rights(rights) for rights in value or []],
    "types": _normalize_types,
    "publicationYear": lambda value: (
        int(value) if isinstance(value, str) and value.isdigit() else value
    ),
    "container": lambda value: value or {},
}


def _normalize(field: str, value):
    if field in NORMALIZERS:
        return NORMALIZERS[field](value)
    return value if field in SCALAR_FIELDS else value or []


def _xml_element(name: str, text=None, *, indent: int = 4, **attributes) -> str:
    rendered = "".join(
        f' {key}="{escape(str(value), XML_ATTRIBUTE_ENTITIES)}"'
        for key, value in attributes.items()
        if value is not None
    )
    if text in (None, ""):
        return f"{' ' * indent}<{name}{rendered}/>"
    return f"{' ' * indent}<{name}{rendered}>{escape(str(text))}</{name}>"


def _xml_list(name: str, elements: list[str]) -> list[str]:
    return [f"  <{name}>", *elements, f"  </{name}>"] if elements else [f"  <{name}/>"]


def _cited_by(related: dict) -> dict:
    type_ = related.get("resourceTypeGeneral") or "ScholarlyArticle"
    if related.get("relatedIdentifierType") == "DOI":
        return {"@id": f"https://doi.org/{related.get('relatedIdentifier')}", "@type": type_}
    return {
        "@type": type_,
        "identifier": {
            "@type": "PropertyValue",
            "propertyID": related.get("relatedIdentifierType"),
            "value": related.get("relatedIdentifier"),
        },
    }


class Record:
    def __init__(self, doi: str):
        self.doi = doi
        self.metadata: dict = {field: _normalize(field, None) for field in METADATA_FIELDS}
        self.has_metadata = False
        self.url: str | None = None
        self.schema_version: str | None = None
        self.state = "draft"
        self.created = self.updated = datetime.now(UTC)
        self.registered: datetime | None = None
        self.metadata_version = 0

    def update(self, attributes: dict) -> None:
        """Apply attributes and an optional event, validating any registered or findable DOI."""
        for field in METADATA_FIELDS:
            if field in attributes:
                self.metadata[field] = _normalize(field, attributes[field])
                self.has_metadata = True
        self.url = attributes.get("url", self.url)
        self.schema_version = attributes.get("schemaVersion", self.schema_version)

        event = attributes.get("event")
        if event == "publish":
            self.state = "findable"
        elif (event == "register" and self.state == "draft") or (
            event == "hide" and self.state == "findable"
        ):
            self.state = "registered"

        if self.state != "draft":
            self.validate()
            self.registered = self.registered or datetime.now(UTC)

    @property
    def title(self) -> str | None:
        return self.metadata["titles"][0].get("title") if self.metadata["titles"] else None

    @property
    def publication_year(self) -> str | None:
        year = self.metadata["publicationYear"]
        return str(year) if year not in (None, "") else None

    def xml_lines(self) -> list[str]:
        m = self.metadata
        creators = []
        for creator in m["creators"]:
            creators += [
                "    <creator>",
                _xml_element("creatorName", creator.get("name"), indent=6),
                "    </creator>",
            ]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns="http://datacite.org/schema/kernel-4" '
            'xsi:schemaLocation="http://datacite.org/schema/kernel-4 '
            'http://schema.datacite.org/meta/kernel-4/metadata.xsd">',
            _xml_element("identifier", self.doi.upper(), indent=2, identifierType="DOI"),
            *_xml_list("creators", creators),
            *_xml_list("titles", [_xml_element("title", t.get("title")) for t in m["titles"]]),
            _xml_element("publisher", m["publisher"], indent=2),
            _xml_element("publicationYear", self.publication_year, indent=2),
        ]
        if m["types"]:
            lines.append(
                _xml_element(
                    "resourceType",
                    m["types"].get("resourceType"),
                    indent=2,
                    resourceTypeGeneral=m["types"]["resourceTypeGeneral"],
                )
            )
        if m["relatedIdentifiers"]:
            lines += _xml_list(
                "relatedIdentifiers",
                [
                    _xml_element(
                        "relatedIdentifier",
                        r.get("relatedIdentifier"),
                        relatedIdentifierType=r.get("relatedIdentifierType"),
                        relationType=r.get("relationType"),
                    )
                    for r in m["relatedIdentifiers"]
                ],
            )
        lines += ["  <sizes/>", "  <formats/>", _xml_element("version", m["version"], indent=2)]
        if m["rightsList"]:
            lines += _xml_list(
                "rightsList",
                [
                    _xml_element(
                        "rights",
                        r.get("rights"),
                        rightsURI=r.get("rightsUri"),
                        rightsIdentifier=r.get("rightsIdentifier"),
                        rightsIdentifierScheme=r.get("rightsIdentifierScheme"),
                        schemeURI=r.get("schemeUri"),
                    )
                    for r in m["rightsList"]
                ],
            )
        if m["descriptions"]:
            lines += _xml_list(
                "descriptions",
                [
                    _xml_element(
                        "description",
                        d.get("description"),
                        descriptionType=d.get("descriptionType"),
                    )
                    for d in m["descriptions"]
                ],
            )
        return [*lines, "</resource>"]

    def xml(self) -> str | None:
        return "\n".join(self.xml_lines()) + "\n" if self.has_metadata else None

    def schema_error(self) -> tuple[str, str] | None:
        """Return the first error DataCite's XSD validation reports, as (source, message)."""
        missing_child = "Missing child element(s). Expected is ( {}{} )."
        for number, line in enumerate(self.xml_lines(), start=1):
            location = f"at line {number}, column 0"
            match line.strip():
                case "<creators/>":
                    return "creators", f"{missing_child.format(KERNEL_NS, 'creator')} {location}"
                case "<titles/>":
                    return "titles", f"{missing_child.format(KERNEL_NS, 'title')} {location}"
                case "<publisher/>":
                    return (
                        "publisher",
                        "[facet 'minLength'] The value has a length of '0'; this underruns the "
                        f"allowed minimum length of '1'. {location}",
                    )
                case "<publicationYear/>":
                    return (
                        "publication_year",
                        "[facet 'pattern'] The value '' is not accepted by the pattern "
                        f"'[\\d]{{4}}'. {location}",
                    )
        if not self.metadata["types"]:
            expected = ", ".join(
                f"{KERNEL_NS}{child}"
                for child in [
                    "resourceType",
                    "subjects",
                    "contributors",
                    "dates",
                    "language",
                    "alternateIdentifiers",
                    "relatedIdentifiers",
                    "geoLocations",
                    "fundingReferences",
                    "relatedItems",
                ]
            )
            return (
                "xml",
                f"Missing child element(s). Expected is one of ( {expected} ). at line 2, column 0",
            )
        return None

    def validate(self) -> None:
        if not self.url:
            raise _field_error("url", "Can't be blank", self.doi)
        if not self.has_metadata:
            raise _field_error("xml", "Can't be blank", self.doi)
        if error := self.schema_error():
            raise _field_error(error[0], f"DOI {self.doi}: {error[1]}", self.doi)

    def to_json(self, *, client_id: str, from_storage: bool, include_landing_page: bool) -> dict:
        metadata = self.metadata
        if from_storage:
            # MySQL returns JSON columns with object keys sorted by length, then bytes
            metadata = {
                field: value if field in SCALAR_FIELDS else _mysql_json_order(value)
                for field, value in metadata.items()
            }
        prefix, _, suffix = self.doi.partition("/")
        xml = self.xml()
        attributes = {
            "doi": self.doi,
            "prefix": prefix,
            "suffix": suffix,
            **metadata,
            "xml": base64.b64encode(xml.encode()).decode() if xml else None,
            "url": self.url,
            "contentUrl": None,
            "metadataVersion": self.metadata_version,
            "schemaVersion": self.schema_version,
            "source": "api",
            "isActive": self.state == "findable",
            "state": self.state,
            "reason": None,
            "landingPage": None,
            "viewCount": 0,
            "viewsOverTime": [],
            "downloadCount": 0,
            "downloadsOverTime": [],
            "referenceCount": 0,
            "citationCount": 0,
            "citationsOverTime": [],
            "partCount": 0,
            "partOfCount": 0,
            "versionCount": 0,
            "versionOfCount": 0,
            "created": _timestamp(self.created),
            "registered": _timestamp(self.registered),
            "published": self.publication_year or "",
            "updated": _timestamp(self.updated),
        }
        if not include_landing_page:
            del attributes["landingPage"]
        return {
            "data": {
                "id": self.doi,
                "type": "dois",
                "attributes": attributes,
                "relationships": {
                    "client": {"data": {"id": client_id, "type": "clients"}},
                    "provider": {"data": {"id": client_id.split(".", 1)[0], "type": "providers"}},
                    "media": {"data": {"id": self.doi, "type": "media"}},
                    **{name: {"data": []} for name in EMPTY_RELATIONSHIPS},
                },
            }
        }

    def to_schema_org(self) -> dict:
        m = self.metadata
        person_types = {"Personal": "Person", "Organizational": "Organization"}
        authors = [
            _compact(
                {
                    "@type": person_types.get(creator.get("nameType")),
                    "name": creator.get("name"),
                    "givenName": creator.get("givenName"),
                    "familyName": creator.get("familyName"),
                }
            )
            for creator in m["creators"]
        ]
        abstracts = [d for d in m["descriptions"] if d.get("descriptionType") == "Abstract"]
        cited_by = [
            _cited_by(r)
            for r in m["relatedIdentifiers"]
            if r.get("relationType") == "IsReferencedBy"
        ]
        return _compact(
            {
                "@context": "http://schema.org",
                "@type": m["types"].get("schemaOrg"),
                "@id": f"https://doi.org/{self.doi}",
                "url": self.url,
                "name": self.title,
                "author": _unwrap(authors),
                "description": abstracts[0].get("description") if abstracts else None,
                "license": _unwrap([r["rightsUri"] for r in m["rightsList"] if "rightsUri" in r]),
                "datePublished": m["publicationYear"],
                "@reverse": {"citation": _unwrap(cited_by)} if cited_by else None,
                "schemaVersion": self.schema_version,
                "publisher": {"@type": "Organization", "name": m["publisher"]}
                if m["publisher"] is not None
                else None,
                "provider": {"@type": "Organization", "name": "datacite"},
            }
        )

    @property
    def citable(self) -> bool:
        return bool(self.metadata["types"]) and self.metadata["publisher"] is not None

    def to_citation(self, style_name: str) -> str:
        style = CITATION_STYLES.get(style_name, CITATION_STYLES["apa"])
        title = self.title or ""
        if style.title_case:
            title = _title_case(title)
        m = self.metadata
        citation = Citation(
            authors=_authors(
                [_html(creator.get("name")) for creator in m["creators"]], style.names
            ),
            title=_html(title),
            year=self.publication_year,
            publisher=_html(m["publisher"]),
            doi=self.doi,
            url=_html(self.url),
            resource_type=m["types"].get("resourceTypeGeneral"),
        )
        return style.render(citation)


def _unwrap(items: list):
    if not items:
        return None
    return items[0] if len(items) == 1 else items


class Citation(NamedTuple):
    authors: str
    title: str
    year: str | None
    publisher: str
    doi: str
    url: str
    resource_type: str | None


class NameRule(NamedTuple):
    """How a style lists names: after et_al_min names, keep use_first and append et_al."""

    et_al_min: int
    use_first: int
    et_al: str
    last_delimiter: str
    two_delimiter: str | None = None
    use_last: bool = False


class _Italic(str):
    __slots__ = ()


def _cat(*pieces: str) -> str:
    """Concatenate like citeproc-ruby, which drops a space where two spaces would meet."""
    rendered, text = [], ""
    for piece in pieces:
        if not piece:
            continue
        squeezed = type(piece)(piece[1:]) if text.endswith(" ") and piece.startswith(" ") else piece
        text += squeezed
        rendered.append(f"<i>{squeezed}</i>" if isinstance(squeezed, _Italic) else squeezed)
    return "".join(rendered)


def _html(value: str | None) -> str:
    return value.replace("&", "&amp;") if value else ""


def _terminate(value: str) -> str:
    return value if value.endswith((".", "?", "!")) else f"{value}."


def _quote(title: str) -> str:
    inner = "\N{LEFT SINGLE QUOTATION MARK}\\1\N{RIGHT SINGLE QUOTATION MARK}"
    title = re.sub(r'"([^"]*)"', inner, title)
    title = re.sub(
        "\N{LEFT DOUBLE QUOTATION MARK}([^\N{RIGHT DOUBLE QUOTATION MARK}]*)"
        "\N{RIGHT DOUBLE QUOTATION MARK}",
        inner,
        title,
    )
    return f"\N{LEFT DOUBLE QUOTATION MARK}{_terminate(title)}\N{RIGHT DOUBLE QUOTATION MARK}"


_TITLE_WORD = re.compile(r"\b([^\W\d_])((?:[^\W\d_]|\.)+)\b")
_TITLE_LAST_WORD = re.compile(r"(\.|\b)([^\W\d_])([^\W\d_]+)\b$")


def _title_case(title: str) -> str:
    first = True

    def capitalize(match: re.Match) -> str:
        nonlocal first
        if match.group(0).lower() in STOP_WORDS and not first:
            return match.group(0)
        first = False
        return match.group(1).upper() + match.group(2)

    def capitalize_last(match: re.Match) -> str:
        if match.group(1) == "." or not match.group(2).islower():
            return match.group(0)
        return match.group(1) + match.group(2).upper() + match.group(3)

    return _TITLE_LAST_WORD.sub(capitalize_last, _TITLE_WORD.sub(capitalize, title))


def _join_names(names: list[str], last_delimiter: str) -> str:
    pieces = []
    for index, name in enumerate(names):
        if index:
            pieces.append(last_delimiter if index == len(names) - 1 else ", ")
        pieces.append(name)
    return _cat(*pieces)


def _authors(names: list[str], rule: NameRule) -> str:
    if len(names) >= rule.et_al_min:
        # appended without squeezing, so a name's trailing space survives before the term
        authors = _join_names(names[: rule.use_first], ", ") + rule.et_al
        return _cat(authors, names[-1]) if rule.use_last else authors
    if rule.two_delimiter and len(names) == 2:
        return _join_names(names, rule.two_delimiter)
    return _join_names(names, rule.last_delimiter)


def _apa(c: Citation) -> str:
    label = APA_TYPE_LABELS.get(c.resource_type)
    date = [f"({c.year})", ". "] if c.year else []
    if c.authors:
        pieces = [_terminate(c.authors), " ", *date]
        if c.title:
            pieces += [_Italic(c.title), f" [{label}]" if label else "", ". "]
    elif c.title:
        pieces = [_Italic(c.title), ". ", *date, f"[{label}]. " if label else ""]
    else:
        pieces = date
    if c.publisher:
        pieces += [_terminate(c.publisher), " "]
    return _cat(*pieces, f"https://doi.org/{c.doi}")


def _harvard(c: Citation) -> str:
    pieces = [c.authors, " "] if c.authors else []
    pieces.append(f"({c.year})" if c.year else "(no date)")
    pieces += [" ", _quote(c.title), " "] if c.title else [". "]
    if c.publisher:
        pieces += [_terminate(c.publisher), " "]
    return _cat(*pieces, f"Available at: https://doi.org/{c.doi}.")


def _mla(c: Citation) -> str:
    pieces = [_terminate(c.authors), " "] if c.authors else []
    if c.title:
        pieces += [_quote(c.title), " "]
    tail = ", ".join(part for part in (c.publisher, c.year, f"https://doi.org/{c.doi}") if part)
    return _cat(*pieces, f"{tail}.")


def _vancouver(c: Citation) -> str:
    pieces = [_terminate(c.authors), " "] if c.authors else []
    if c.url:
        pieces += [c.title, " [Internet]", ". "]
    elif c.title:
        pieces += [_terminate(c.title), " "]
    if c.publisher:
        pieces += [c.publisher, "; "]
    if c.year:
        pieces += [c.year, ". "]
    if c.url:
        pieces += ["Available from: ", c.url]
    return _cat(*pieces)


def _ieee(c: Citation) -> str:
    pieces = [c.authors, ", "] if c.authors else []
    if c.title:
        pieces += [_quote(c.title), " "]
    pieces.append(", ".join(part for part in (c.publisher, c.year) if part))
    return _cat(*pieces, f". doi: {c.doi}.")


class Style(NamedTuple):
    render: Callable[[Citation], str]
    names: NameRule
    title_case: bool = False


CITATION_STYLES = {
    "apa": Style(_apa, NameRule(21, 19, ", \N{HORIZONTAL ELLIPSIS} ", ", &amp; ", use_last=True)),
    "harvard-cite-them-right": Style(_harvard, NameRule(4, 1, " <i>et al.</i>", " and ")),
    "modern-language-association": Style(
        _mla, NameRule(3, 1, ", et al.", ", and "), title_case=True
    ),
    "vancouver": Style(_vancouver, NameRule(7, 6, ", et al", ", ")),
    "ieee": Style(_ieee, NameRule(7, 1, " <i>et al.</i>", ", and ", two_delimiter=" and ")),
}


class Registry:
    def __init__(self, *, client_id: str, password: str, prefixes: list[str]):
        self.client_id = client_id.lower()
        self.password = password
        self.prefixes = {prefix.lower() for prefix in prefixes}
        self.records: dict[str, Record] = {}
        self.lock = threading.Lock()

    def check_doi(self, doi: str) -> None:
        if not DOI_PATTERN.match(doi) or doi.split("/", 1)[0] not in self.prefixes:
            raise _status_error(HTTPStatus.FORBIDDEN, FORBIDDEN)

    def create(self, doi: str, attributes: dict) -> Record:
        record = Record(doi)
        record.update(attributes)
        self.records[doi] = record
        return record

    def update(self, record: Record, attributes: dict) -> Record:
        """Update a copy of the record, replacing the stored one only if the update succeeds."""
        candidate = copy.deepcopy(record)
        candidate.update(attributes)
        candidate.updated = datetime.now(UTC)
        if candidate.xml() != record.xml():
            candidate.metadata_version += 1
        self.records[record.doi] = candidate
        return candidate


def _parse_attributes(raw: bytes) -> dict:
    try:
        body = json.loads(raw or b"null")
    except ValueError as e:
        raise _status_error(
            HTTPStatus.BAD_REQUEST, "Error occurred while parsing request parameters"
        ) from e
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict) or not body["data"]:
        raise _status_error(
            HTTPStatus.BAD_REQUEST, "You need to provide a payload following the JSONAPI spec"
        )
    attributes = body["data"].get("attributes")
    if not attributes or not isinstance(attributes, dict):
        raise _status_error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "param is missing or the value is empty or invalid: attributes",
        )
    return attributes


def _negotiate(accept: str) -> str:
    for media_range in accept.split(","):
        media_type = media_range.split(";", 1)[0].strip().lower()
        if media_type in (SCHEMA_ORG_TYPE, BIBLIOGRAPHY_TYPE, DATACITE_XML_TYPE):
            return media_type
    return "application/json"


app = Flask(__name__)


def _registry() -> Registry:
    return current_app.config["DATACITE_REGISTRY"]


def _response(status: HTTPStatus, body, content_type: str = JSON_TYPE, headers=None) -> Response:
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return Response(body, status=status, content_type=content_type, headers=headers)


def _record_response(status: HTTPStatus, record: Record, headers=None) -> Response:
    body = record.to_json(
        client_id=_registry().client_id, from_storage=False, include_landing_page=True
    )
    return _response(status, body, headers=headers)


def _authenticated() -> bool | None:
    """Return whether the credentials are valid, or None when none were sent."""
    auth = request.authorization
    if auth is None or auth.type != "basic":
        return None
    registry = _registry()
    return (auth.username or "").lower() == registry.client_id and (
        auth.password == registry.password
    )


def _require_credentials() -> None:
    authenticated = _authenticated()
    if authenticated is None:
        raise _status_error(HTTPStatus.UNAUTHORIZED, "Bad credentials.")
    if not authenticated:
        raise _status_error(HTTPStatus.NOT_FOUND, NOT_FOUND)


def _locked(view):
    @functools.wraps(view)
    def locked_view(*args, **kwargs):
        with _registry().lock:
            return view(*args, **kwargs)

    return locked_view


@app.errorhandler(ApiError)
def _api_error(e: ApiError) -> Response:
    return _response(e.status, {"errors": e.errors}, e.content_type)


@app.errorhandler(HTTPStatus.NOT_FOUND)
def _not_found(e) -> Response:
    return _api_error(_status_error(HTTPStatus.NOT_FOUND, NOT_FOUND))


@app.after_request
def _credential_header(response: Response) -> Response:
    if _authenticated():
        response.headers["X-Credential-Username"] = _registry().client_id
    return response


@app.get("/heartbeat")
def heartbeat() -> Response:
    return _response(HTTPStatus.OK, "OK", "text/plain; charset=utf-8")


@app.post("/_mock/reset")
@_locked
def reset() -> Response:
    _registry().records.clear()
    return _response(HTTPStatus.NO_CONTENT, "", "text/plain; charset=utf-8")


@app.get("/dois/<path:doi>")
@_locked
def get_doi(doi: str) -> Response:
    record = _registry().records.get(doi.lower().rstrip("/"))
    authenticated = bool(_authenticated())
    if not record or (record.state != "findable" and not authenticated):
        raise _status_error(HTTPStatus.NOT_FOUND, NOT_FOUND)

    media_type = _negotiate(request.headers.get("Accept", ""))
    content_type = f"{media_type}; charset=utf-8"
    if media_type == SCHEMA_ORG_TYPE:
        return _response(HTTPStatus.OK, record.to_schema_org(), content_type)
    if media_type == BIBLIOGRAPHY_TYPE:
        if not record.citable:
            raise _status_error(
                HTTPStatus.BAD_REQUEST, "undefined method '[]' for nil", content_type
            )
        citation = record.to_citation(request.args.get("style", "apa"))
        return _response(HTTPStatus.OK, citation, content_type)
    if media_type == DATACITE_XML_TYPE and record.has_metadata:
        return _response(HTTPStatus.OK, record.xml(), content_type)
    body = record.to_json(
        client_id=_registry().client_id, from_storage=True, include_landing_page=authenticated
    )
    return _response(HTTPStatus.OK, body)


@app.post("/dois")
@_locked
def create_doi() -> Response:
    _require_credentials()
    attributes = _parse_attributes(request.get_data())
    if attributes.get("doi"):
        doi = str(attributes["doi"]).lower()
    elif attributes.get("prefix"):
        doi = f"{str(attributes['prefix']).lower()}/{_generate_suffix()}"
    else:
        doi = ""
    registry = _registry()
    registry.check_doi(doi)
    if doi in registry.records:
        raise _field_error("doi", "This DOI has already been taken", doi)
    record = registry.create(doi, attributes)
    location = f"http://{request.host}/dois/{len(registry.records)}"
    return _record_response(HTTPStatus.CREATED, record, {"Location": location})


@app.put("/dois/<path:doi>")
@_locked
def put_doi(doi: str) -> Response:
    _require_credentials()
    attributes = _parse_attributes(request.get_data())
    doi = doi.lower().rstrip("/")
    registry = _registry()
    registry.check_doi(doi)
    if record := registry.records.get(doi):
        return _record_response(HTTPStatus.OK, registry.update(record, attributes))
    return _record_response(HTTPStatus.CREATED, registry.create(doi, attributes))


def main() -> None:
    parser = argparse.ArgumentParser(description="A stand-in for the DataCite REST API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--client-id", default="mock.isic", help="repository ID, the username")
    parser.add_argument("--password", default="password")
    parser.add_argument(
        "--prefix",
        action="append",
        dest="prefixes",
        help="DOI prefix the repository owns (repeatable, default 10.80222)",
    )
    args = parser.parse_args()

    app.config["DATACITE_REGISTRY"] = Registry(
        client_id=args.client_id, password=args.password, prefixes=args.prefixes or ["10.80222"]
    )
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
