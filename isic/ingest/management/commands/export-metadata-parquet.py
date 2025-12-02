from itertools import batched
from pathlib import Path
from typing import Annotated

from annotated_types import Ge
import djclick as click
from isic_metadata.metadata import MetadataRow
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic_to_pyarrow import get_pyarrow_schema

from isic.core.models import Image

ROW_GROUP_SIZE = 10_000


class ParquetMetadataRow(MetadataRow):
    age_approx: Annotated[int, Ge(0)] | None = None


@click.command(help="Export the metadata for a set of images to a parquet file")
@click.argument("parquet_path", type=str)
@click.option("--public", is_flag=True, default=True)
def export_metadata_parquet(parquet_path: str, *, public: bool = True):
    """Export the metadata for a set of images to a parquet file."""
    output_path = Path(parquet_path)
    schema = get_pyarrow_schema(ParquetMetadataRow, exclude_fields=True)

    for field in ["age", "marker_pen", "blurry", "hairy", "color_tint"]:
        schema = schema.remove(schema.get_field_index(field))

    rows = (
        ParquetMetadataRow(**image.metadata)
        for image in Image.objects.filter(public=public).select_related("accession").iterator()
    )

    with pq.ParquetWriter(output_path, schema) as writer:
        for batch in batched(rows, ROW_GROUP_SIZE):
            row_dicts = [row.model_dump(mode="python") for row in batch]
            table = pa.Table.from_pylist(row_dicts, schema=schema)
            writer.write_table(table)
