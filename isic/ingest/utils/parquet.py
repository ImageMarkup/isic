from typing import Annotated

from annotated_types import Ge
from isic_metadata.metadata import MetadataRow
import pyarrow as pa
from pydantic_to_pyarrow import get_pyarrow_schema

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


def build_parquet_schema(parquet_metadata: dict | None = None) -> pa.Schema:
    schema = get_pyarrow_schema(ParquetMetadataRow, exclude_fields=True)

    for field in EXCLUDED_FIELDS:
        schema = schema.remove(schema.get_field_index(field))

    schema = pa.schema([schema.field(name) for name in FIELD_ORDER])

    if parquet_metadata:
        schema = schema.with_metadata(parquet_metadata)

    return schema
