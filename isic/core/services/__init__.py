from collections.abc import Generator
from functools import reduce
import operator
from typing import Any, cast

from django.db.models import F, Func
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = "jsonb_object_keys"


def staff_image_metadata_csv(*, qs: QuerySet[Image]) -> Generator[list[str] | dict[str, Any]]:
    """
    Generate a CSV of image metadata for staff users.

    This includes all metadata, including sensitive metadata, and private remapped ids.
    It also includes cohort and attribution info, and the original filename.

    The first value yielded is the header row, and subsequent values are the rows of the CSV.
    """
    headers = [
        "original_filename",
        "isic_id",
        "cohort_id",
        "cohort",
        "attribution",
        "copyright_license",
        "public",
    ]
    for field in Accession.computed_fields:
        headers.append(field.input_field_name)
        headers += field.output_field_names

    accession_qs = Accession.objects.filter(image__in=qs)

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    counts = accession_qs.aggregate(**{k: Count(k) for k in Accession.metadata_keys()})
    used_metadata_keys = [k for k, v in counts.items() if v > 0]

    # strip out any keys that are already in the headers. this is to strip out the
    # input_field_names from Accession.computed_fields.
    used_metadata_keys = [v for v in used_metadata_keys if v not in headers]

    used_unstructured_metadata_keys = list(
        accession_qs.annotate(unstructured_metadata_keys=JsonKeys("unstructured_metadata__value"))
        .order_by()
        .values_list("unstructured_metadata_keys", flat=True)
        .distinct()
    )

    remapped_keys: list[str] = reduce(
        operator.iadd,
        [
            [field.internal_id_name, field.csv_field_name]
            for field in Accession.remapped_internal_fields
        ],
        [],
    )

    yield (
        headers
        + sorted(used_metadata_keys)
        + remapped_keys
        + sorted([f"unstructured.{key}" for key in used_unstructured_metadata_keys])
    )

    # avoid calling this multiple times, since it adds up when exporting significant numbers of
    # images.
    accession_metadata_keys = Accession.metadata_keys()

    # Note this uses .values because populating django ORM objects is very slow, and doing this
    # on large querysets can add ~5s per 100k images to the request time.
    for image in (
        qs.order_by("isic_id")
        .values(
            "accession__original_blob_name",
            "isic_id",
            "accession__cohort_id",
            "accession__cohort__name",
            "accession__attribution",
            "accession__copyright_license",
            "public",
            *[f"accession__{key}" for key in used_metadata_keys],
            *[f"accession__{field.csv_field_name}" for field in Accession.remapped_internal_fields],
            *[f"accession__{field.input_field_name}" for field in Accession.computed_fields],
            *[
                f"accession__{field.relation_name}__{field.internal_id_name}"
                for field in Accession.remapped_internal_fields
            ],
            "accession__unstructured_metadata__value",
        )
        .iterator()
    ):
        value = {
            "original_filename": image["accession__original_blob_name"],
            "isic_id": image["isic_id"],
            "cohort_id": image["accession__cohort_id"],
            "cohort": image["accession__cohort__name"],
            "attribution": image["accession__attribution"],
            "copyright_license": image["accession__copyright_license"],
            "public": image["public"],
            **{
                k.replace("accession__", ""): v
                for k, v in image.items()
                if k.replace("accession__", "") in accession_metadata_keys
            },
            **{
                field.internal_id_name: image[
                    f"accession__{field.relation_name}__{field.internal_id_name}"
                ]
                for field in Accession.remapped_internal_fields
            },
            **{
                field.csv_field_name: image[f"accession__{field.csv_field_name}"]
                for field in Accession.remapped_internal_fields
            },
            **{
                f"unstructured.{k}": v
                for k, v in image["accession__unstructured_metadata__value"].items()
            },
        }

        for field in Accession.computed_fields:
            computed_output_fields = field.transformer(
                image[f"accession__{field.input_field_name}"]
                if image.get(f"accession__{field.input_field_name}")
                else None
            )

            if computed_output_fields:
                value.update(computed_output_fields)

        yield value


def image_metadata_csv(*, qs: QuerySet[Image]) -> tuple[list[str], Generator[dict[str, Any]]]:
    """
    Generate the fieldnames and rows of a CSV of image metadata for non-staff users.

    The fieldnames are computed eagerly, and the rows are a generator.
    """
    initial_headers = ["isic_id", "attribution", "copyright_license"]

    accession_qs = Accession.objects.filter(image__in=qs)

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    counts = accession_qs.aggregate(**{k: Count(k) for k in Accession.metadata_keys()})
    used_metadata_columns = [k for k, v in counts.items() if v > 0]

    # A remapped field's csv_field_name (e.g. lesion_id) is also the name of the FK column on
    # Accession. Further, since these remapped fields all use natural PKs, we can read the values
    # directly off the accession without a join.
    used_remapped_columns = [
        field.csv_field_name
        for field in Accession.remapped_internal_fields
        if accession_qs.exclude(**{field.relation_name: None}).exists()
    ]

    used_computed_fields = [
        computed_field
        for computed_field in Accession.computed_fields
        if computed_field.input_field_name in used_metadata_columns
    ]

    used_metadata_keys = used_metadata_columns + used_remapped_columns
    for computed_field in used_computed_fields:
        used_metadata_keys.remove(computed_field.input_field_name)
        used_metadata_keys += computed_field.output_field_names

    fieldnames = initial_headers + sorted(used_metadata_keys)

    def rows() -> Generator[dict[str, Any]]:
        # Note this uses .values because populating django ORM objects is very slow, and doing
        # this on large querysets can add ~5s per 100k images to the request time. Only the
        # columns in use are selected, and they're aliased to their CSV names in the query so
        # that no per-row key renaming is needed.
        for image in (
            qs.order_by("isic_id")
            .values(
                "isic_id",
                attribution=F("accession__attribution"),
                copyright_license=F("accession__copyright_license"),
                **{
                    key: F(f"accession__{key}")
                    for key in used_metadata_columns + used_remapped_columns
                },
            )
            .iterator()
        ):
            # Strip the TypedDict, since we're about to change some fields
            row = cast("dict[str, Any]", image)

            for computed_field in used_computed_fields:
                input_value = row.pop(computed_field.input_field_name)
                if input_value:
                    computed_values = computed_field.transformer(input_value)
                    if computed_values:
                        row.update(computed_values)

            yield row

    return fieldnames, rows()
