from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.ingest.models.lesion import Lesion

MODALITIES = {
    "dermoscopic": "Dermoscopic",
    "clinical": "Clinical",
    "tbp": "Total Body Photography",
    "rcm": "Reflectance Confocal Microscopy",
}


def lesion_detail(request, identifier):
    qs = get_visible_objects(
        request.user,
        "ingest.view_lesion",
        Lesion.objects.with_total_info().prefetch_related(
            "accessions__image", "accessions__cohort"
        ),
    )
    lesion = get_object_or_404(qs, pk=identifier)

    images = (
        get_visible_objects(
            request.user,
            "core.view_image",
            Image.objects.filter(accession__lesion=lesion),
        )
        .select_related("accession")
        .order_by("accession__acquisition_day")
    )

    images_list = [
        {
            "id": image.accession.id,
            "full_url": image.accession.blob.url
            if not settings.ISIC_PLACEHOLDER_IMAGES
            else f"https://picsum.photos/seed/{image.accession.id}/256",
            "modality": next(
                modality
                for modality in MODALITIES
                if image.accession.image_type.startswith(modality)
            )
            if image.accession.image_type
            else None,
            "isic_id": image.isic_id,
            "image_detail_url": reverse("core/image-detail", args=[image.id]),
            "acquisition_day": image.accession.acquisition_day,
        }
        for image in images
    ]
    images_by_modality = {
        modality: [image for image in images_list if image["modality"] == modality]
        for modality in MODALITIES
    }

    ctx = {
        "lesion": lesion,
        "images_by_modality": images_by_modality,
        "MODALITIES": MODALITIES,
    }

    return render(request, "core/lesion_detail.html", ctx)
