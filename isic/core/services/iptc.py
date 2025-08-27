from django.core.files import File

from isic.core.models.image import Image
from isic.ingest.services.publish import embed_iptc_metadata


def embed_iptc_metadata_for_image(image: Image, *, ignore_public_check=False) -> None:
    # this is designed to embed IPTC metadata in the image before unembargoing
    if not ignore_public_check and image.public:
        raise ValueError("Cannot embed IPTC metadata for public images.")

    accession = image.accession
    attribution = accession.attribution
    copyright_license = accession.copyright_license
    isic_id = image.isic_id

    with (
        embed_iptc_metadata(
            accession.blob,
            attribution,
            copyright_license,
            isic_id,
        ) as blob_with_iptc,
        embed_iptc_metadata(
            accession.thumbnail_256,
            attribution,
            copyright_license,
            isic_id,
        ) as thumbnail_with_iptc,
    ):
        accession.blob = File(
            blob_with_iptc,
            name=f"{isic_id}.{accession.extension}",
        )
        accession.thumbnail_256 = File(
            thumbnail_with_iptc,
            name=f"{isic_id}_thumbnail.jpg",
        )
        accession.save(update_fields=["blob", "thumbnail_256"])
