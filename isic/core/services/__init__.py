from collections.abc import Iterator

from django.db.models import Func
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = "jsonb_object_keys"


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
    for image in qs.order_by("isic_id").values(
        "isic_id",
        "accession__cohort__attribution",
        "accession__copyright_license",
        "accession__metadata",
        "accession__lesion_id",
        "accession__patient_id",
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
