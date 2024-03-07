from collections.abc import Iterable, Iterator

from django.db.models import Func
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = "jsonb_object_keys"


def full_image_metadata_csv_headers(*, qs: QuerySet[Image]) -> list[str]:
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
    used_metadata_keys = list(
        accession_qs.annotate(metadata_keys=JsonKeys("metadata"))
        .order_by()
        .values_list("metadata_keys", flat=True)
        .distinct()
    )

    used_unstructured_metadata_keys = list(
        accession_qs.annotate(unstructured_metadata_keys=JsonKeys("unstructured_metadata__value"))
        .order_by()
        .values_list("unstructured_metadata_keys", flat=True)
        .distinct()
    )

    return (
        headers
        + sorted(used_metadata_keys)
        + ["private_lesion_id", "lesion_id", "private_patient_id", "patient_id"]
        + sorted([f"unstructured.{key}" for key in used_unstructured_metadata_keys])
    )


def full_image_metadata_csv_rows(*, qs: QuerySet[Image]) -> Iterable[dict]:
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
            "accession__metadata",
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
                    Accession._age_approx(image["accession__metadata"]["age"])
                    if image["accession__metadata"].get("age")
                    else None
                ),
                **image["accession__metadata"],
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


def image_metadata_csv_headers(*, qs: QuerySet[Image]) -> list[str]:
    headers = ["isic_id", "attribution", "copyright_license"]

    accession_qs = Accession.objects.filter(image__in=qs)

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    used_metadata_keys = list(
        accession_qs.annotate(metadata_keys=JsonKeys("metadata"))
        .order_by()
        .values_list("metadata_keys", flat=True)
        .distinct()
    )

    if accession_qs.exclude(lesion=None).exists():
        used_metadata_keys.append("lesion_id")

    if accession_qs.exclude(patient=None).exists():
        used_metadata_keys.append("patient_id")

    # TODO: this is a very leaky part of sensitive metadata handling that
    # should be refactored.
    if "age" in used_metadata_keys:
        used_metadata_keys.append("age_approx")
        used_metadata_keys.remove("age")

    return headers + sorted(used_metadata_keys)


def image_metadata_csv_rows(*, qs: QuerySet[Image]) -> Iterator[dict]:
    # Note this uses .values because populating django ORM objects is very slow, and doing this on
    # large querysets can add ~5s per 100k images to the request time.
    for image in (
        qs.order_by("isic_id")
        .values(
            "isic_id",
            "accession__cohort__attribution",
            "accession__copyright_license",
            "accession__metadata",
            "accession__lesion_id",
            "accession__patient_id",
        )
        .iterator()
    ):
        if "age" in image["accession__metadata"]:
            image["accession__metadata"]["age_approx"] = Accession._age_approx(
                image["accession__metadata"]["age"]
            )
            del image["accession__metadata"]["age"]

        if image["accession__lesion_id"]:
            image["accession__metadata"]["lesion_id"] = image["accession__lesion_id"]

        if image["accession__patient_id"]:
            image["accession__metadata"]["patient_id"] = image["accession__patient_id"]

        yield {
            **{
                "isic_id": image["isic_id"],
                "attribution": image["accession__cohort__attribution"],
                "copyright_license": image["accession__copyright_license"],
                **image["accession__metadata"],
            }
        }
