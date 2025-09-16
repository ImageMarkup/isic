from django.shortcuts import get_object_or_404, render

from isic.core.models.doi import Doi, DraftDoi
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

LICENSE_TITLES = {
    "CC-0": "CC0 1.0 Universal",
    "CC-BY": "Attribution 4.0 International",
    "CC-BY-NC": "Attribution-NonCommercial 4.0 International",
}

LICENSE_URIS = {
    "CC-0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-NC": "https://creativecommons.org/licenses/by-nc/4.0/",
}


# @cache_page(timeout=60 * 60 * 24 * 7, key_prefix="doi_detail")
def doi_detail(request, slug):
    try:
        doi = Doi.objects.select_related("collection").get(slug=slug)
    except Doi.DoesNotExist:
        # no permission check here - draft DOIs are unlisted but accessible to anyone
        # with the URL
        doi = get_object_or_404(DraftDoi.objects.select_related("collection"), slug=slug)

    licenses = (
        doi.collection.images.values_list("accession__copyright_license", flat=True)
        .order_by()
        .distinct()
    )

    attributing_institutions = get_attributions(
        doi.collection.images.values_list("accession__attribution", flat=True)
    )

    context = {
        "doi": doi,
        "licenses": licenses,
        "license_descriptions": LICENSE_SHORTHAND_DESCRIPTIONS,
        "license_paths": LICENSE_PATHS,
        "attributing_institutions": attributing_institutions,
        "is_draft": isinstance(doi, DraftDoi),
        "stats": {
            "images": doi.collection.images.count(),
        },
    }

    return render(request, "core/doi_detail.html", context)
