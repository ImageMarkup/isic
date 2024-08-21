from collections.abc import Generator
from functools import reduce
import operator
from typing import Any

from django.db.models import Func
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = "jsonb_object_keys"


def staff_image_metadata_csv(
    *, qs: QuerySet[Image]
) -> Generator[list[str] | dict[str, Any], None, None]:
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

    remapped_keys = reduce(
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

    # Note this uses .values because populating django ORM objects is very slow, and doing this on
    # large querysets can add ~5s per 100k images to the request time.
    for image in (
        qs.order_by("isic_id")
        .values(
            "accession__original_blob_name",
            "isic_id",
            "accession__cohort_id",
            "accession__cohort__name",
            "accession__cohort__attribution",
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
            "attribution": image["accession__cohort__attribution"],
            "copyright_license": image["accession__copyright_license"],
            "public": image["public"],
            **{
                k.replace("accession__", ""): v
                for k, v in image.items()
                if k.replace("accession__", "") in Accession.metadata_keys()
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


def image_metadata_csv(
    *, qs: QuerySet[Image]
) -> Generator[list[str] | dict[str, str | bool | float], None, None]:
    """
    Generate a CSV of image metadata for non-staff users.

    The first value yielded is the header row, and subsequent values are the rows of the CSV.
    """
    headers = ["isic_id", "attribution", "copyright_license"]

    accession_qs = Accession.objects.filter(image__in=qs)

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    counts = accession_qs.aggregate(**{k: Count(k) for k in Accession.metadata_keys()})
    used_metadata_keys = [k for k, v in counts.items() if v > 0]

    for field in Accession.remapped_internal_fields:
        if accession_qs.exclude(**{field.relation_name: None}).exists():
            used_metadata_keys.append(field.csv_field_name)  # noqa: PERF401

    for computed_field in Accession.computed_fields:
        if computed_field.input_field_name in used_metadata_keys:
            used_metadata_keys.remove(computed_field.input_field_name)
            used_metadata_keys += computed_field.output_field_names

    fieldnames = headers + sorted(used_metadata_keys)
    yield fieldnames

    # Note this uses .values because populating django ORM objects is very slow, and doing this on
    # large querysets can add ~5s per 100k images to the request time.
    for image in (
        qs.order_by("isic_id")
        .values(
            "isic_id",
            "accession__cohort__attribution",
            "accession__copyright_license",
            *[f"accession__{key}" for key in Accession.metadata_keys()],
            *[f"accession__{field.csv_field_name}" for field in Accession.remapped_internal_fields],
        )
        .iterator()
    ):
        image = {k.replace("accession__", ""): v for k, v in image.items()}  # noqa: PLW2901

        image["attribution"] = image.pop("cohort__attribution")

        for computed_field in Accession.computed_fields:
            if image[computed_field.input_field_name]:
                computed_fields = computed_field.transformer(image[computed_field.input_field_name])
                if computed_fields:
                    image.update(computed_fields)
                del image[computed_field.input_field_name]

        yield {k: v for k, v in image.items() if k in fieldnames}
