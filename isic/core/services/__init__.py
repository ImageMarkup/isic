from typing import Generator

from django.db.models import Func
from django.db.models.aggregates import Count
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = "jsonb_object_keys"


def staff_image_metadata_csv(
    *, qs: QuerySet[Image]
) -> Generator[list[str] | dict[str, str | bool | float], None, None]:
    """
    Generate a CSV of image metadata for staff users.

    This includes all metadata, including sensitive metadata, and private patient and lesion ids.
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
        "age_approx",
    ]
    accession_qs = Accession.objects.filter(image__in=qs)

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    counts = accession_qs.aggregate(**{k: Count(k) for k in Accession.metadata_keys()})
    used_metadata_keys = [k for k, v in counts.items() if v > 0]

    used_unstructured_metadata_keys = list(
        accession_qs.annotate(unstructured_metadata_keys=JsonKeys("unstructured_metadata__value"))
        .order_by()
        .values_list("unstructured_metadata_keys", flat=True)
        .distinct()
    )

    yield (
        headers
        + sorted(used_metadata_keys)
        + ["private_lesion_id", "lesion_id", "private_patient_id", "patient_id"]
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
            "accession__lesion__private_lesion_id",
            "accession__lesion_id",
            "accession__patient__private_patient_id",
            "accession__patient_id",
            "accession__unstructured_metadata__value",
        )
        .iterator()
    ):
        yield {
            **{
                "original_filename": image["accession__original_blob_name"],
                "isic_id": image["isic_id"],
                "cohort_id": image["accession__cohort_id"],
                "cohort": image["accession__cohort__name"],
                "attribution": image["accession__cohort__attribution"],
                "copyright_license": image["accession__copyright_license"],
                "public": image["public"],
                "age_approx": (
                    Accession._age_approx(image["accession__age"])
                    if image.get("accession__age")
                    else None
                ),
                **{
                    k.replace("accession__", ""): v
                    for k, v in image.items()
                    if k.replace("accession__", "") in Accession.metadata_keys()
                },
                "private_lesion_id": image["accession__lesion__private_lesion_id"],
                "lesion_id": image["accession__lesion_id"],
                "private_patient_id": image["accession__patient__private_patient_id"],
                "patient_id": image["accession__patient_id"],
                **{
                    f"unstructured.{k}": v
                    for k, v in image["accession__unstructured_metadata__value"].items()
                },
            }
        }


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

    if accession_qs.exclude(lesion=None).exists():
        used_metadata_keys.append("lesion_id")

    if accession_qs.exclude(patient=None).exists():
        used_metadata_keys.append("patient_id")

    # TODO: this is a very leaky part of sensitive metadata handling that
    # should be refactored.
    if "age" in used_metadata_keys:
        used_metadata_keys.append("age_approx")
        used_metadata_keys.remove("age")

    yield headers + sorted(used_metadata_keys)

    # Note this uses .values because populating django ORM objects is very slow, and doing this on
    # large querysets can add ~5s per 100k images to the request time.
    for image in (
        qs.order_by("isic_id")
        .values(
            "isic_id",
            "accession__cohort__attribution",
            "accession__copyright_license",
            *[f"accession__{key}" for key in Accession.metadata_keys()],
            "accession__lesion_id",
            "accession__patient_id",
        )
        .iterator()
    ):
        if image["accession__age"]:
            image["age_approx"] = Accession._age_approx(image["accession__age"])
            del image["accession__age"]

        if image["accession__lesion_id"]:
            image["lesion_id"] = image["accession__lesion_id"]
            del image["accession__lesion_id"]

        if image["accession__patient_id"]:
            image["patient_id"] = image["accession__patient_id"]
            del image["accession__patient_id"]

        yield {
            **{
                "isic_id": image["isic_id"],
                "attribution": image["accession__cohort__attribution"],
                "copyright_license": image["accession__copyright_license"],
                **{
                    k: v
                    for k, v in image.items()
                    if k in Accession.metadata_keys()
                    or k in ["age_approx", "lesion_id", "patient_id"]
                },
            }
        }
