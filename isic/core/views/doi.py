from django.shortcuts import get_object_or_404, render

from isic.core.models.doi import Doi
from isic.zip_download.api import get_attributions

LICENSE_SHORTHAND_DESCRIPTIONS = {
    "CC-0": "This content is free to use, modify, and share for any purpose, with no restrictions or attribution required.",  # noqa: E501
    "CC-BY": "This content is free to use, modify, and share as long as you provide credit to the original creator.",  # noqa: E501
    "CC-BY-NC": "This content is free to use, modify, and share for non-commercial purposes, as long as you provide credit to the original creator.",  # noqa: E501
}

LICENSE_PATHS = {
    "CC-0": "core/licenses/cc-0.png",
    "CC-BY": "core/licenses/cc-by.png",
    "CC-BY-NC": "core/licenses/cc-by-nc.png",
}


# @cache_page(timeout=60 * 60 * 24 * 7, key_prefix="doi_detail")
def doi_detail(request, slug):
    doi = get_object_or_404(Doi.objects.select_related("collection"), slug=slug)

    licenses = (
        doi.collection.images.values_list("accession__copyright_license", flat=True)
        .order_by()
        .distinct()
    )

    attributing_institutions = get_attributions(
        doi.collection.images.values_list("accession__cohort__attribution", flat=True)
    )

    context = {
        "doi": doi,
        "licenses": licenses,
        "license_descriptions": LICENSE_SHORTHAND_DESCRIPTIONS,
        "license_paths": LICENSE_PATHS,
        "attributing_institutions": attributing_institutions,
        "stats": {
            "images": doi.collection.images.count(),
            "lesions": doi.collection.images.values_list("accession__lesion_id", flat=True)
            .distinct()
            .count(),
            "patients": doi.collection.images.values_list("accession__patient_id", flat=True)
            .distinct()
            .count(),
        },
    }

    return render(request, "core/doi_detail.html", context)
