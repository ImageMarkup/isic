from datetime import UTC, datetime
from itertools import batched
from pathlib import Path
import sys
import tempfile
from typing import Annotated

from annotated_types import Ge
from django.conf import settings
from django.core.files.storage import storages
import djclick as click
from isic_metadata.metadata import MetadataRow
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic_to_pyarrow import get_pyarrow_schema

from isic.core.models import Image
from isic.core.models.base import CopyrightLicense

ROW_GROUP_SIZE = 10_000

EXCLUDED_FIELDS = ["age", "marker_pen", "blurry", "hairy", "color_tint"]

FIELD_ORDER = [
    "isic_id",
    "attribution",
    "copyright_license",
    "patient_id",
    "age_approx",
    "sex",
    "fitzpatrick_skin_type",
    "personal_hx_mm",
    "family_hx_mm",
    "lesion_id",
    "acquisition_day",
    "clin_size_long_diam_mm",
    "melanocytic",
    "concomitant_biopsy",
    "anatom_site_general",
    "anatom_site_special",
    "anatom_site_1",
    "anatom_site_2",
    "anatom_site_3",
    "anatom_site_4",
    "anatom_site_5",
    "diagnosis_confirm_type",
    "diagnosis_1",
    "diagnosis_2",
    "diagnosis_3",
    "diagnosis_4",
    "diagnosis_5",
    "mel_mitotic_index",
    "mel_thick_mm",
    "mel_ulcer",
    "image_type",
    "dermoscopic_type",
    "tbp_tile_type",
    "image_manipulation",
    "rcm_case_id",
]


class ParquetMetadataRow(MetadataRow):
    isic_id: str
    age_approx: Annotated[int, Ge(0)] | None = None
    attribution: str = ""
    copyright_license: CopyrightLicense | None = None


@click.command(help="Export public image metadata to a parquet file in sponsored storage")
def export_metadata_parquet():
    schema = get_pyarrow_schema(ParquetMetadataRow, exclude_fields=True)

    for field in EXCLUDED_FIELDS:
        schema = schema.remove(schema.get_field_index(field))

    schema = pa.schema([schema.field(name) for name in FIELD_ORDER]).with_metadata(
        {"snapshot_timestamp": datetime.now(tz=UTC).isoformat()}
    )

    qs = Image.objects.filter(public=True).select_related("accession")
    total = qs.count()
    rows = (
        ParquetMetadataRow(
            isic_id=image.isic_id,
            attribution=image.accession.attribution,
            copyright_license=image.accession.copyright_license,
            **image.metadata,
        )
        for image in qs.iterator()
    )

    storage_key = settings.ISIC_DATA_EXPLORER_PARQUET_KEY

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        tmp_path = Path(tmp.name)
        with (
            pq.ParquetWriter(
                tmp.name, schema, use_dictionary=False, compression="snappy"
            ) as writer,
            click.progressbar(length=total, file=sys.stderr) as bar,
        ):
            for batch in batched(rows, ROW_GROUP_SIZE):
                row_dicts = [row.model_dump(mode="python") for row in batch]
                table = pa.Table.from_pylist(row_dicts, schema=schema)
                writer.write_table(table)
                bar.update(len(batch))

        with tmp_path.open("rb") as f:
            storages["sponsored"].save(storage_key, f)

    click.echo(f"Uploaded to storage key: {storage_key}", err=True)
