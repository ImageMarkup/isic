from datetime import UTC, datetime
from itertools import batched
from pathlib import Path
import sys
import tempfile

from django.conf import settings
from django.core.files.storage import storages
import djclick as click
import pyarrow as pa
import pyarrow.parquet as pq

from isic.core.models import Image
from isic.ingest.utils.parquet import (
    ROW_GROUP_SIZE,
    ParquetMetadataRow,
    build_parquet_schema,
)


@click.command(help="Export public image metadata to a parquet file in sponsored storage")
def export_metadata_parquet():
    schema = build_parquet_schema(
        parquet_metadata={"snapshot_timestamp": datetime.now(tz=UTC).isoformat()}
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
            pq.ParquetWriter(tmp.name, schema, compression="snappy") as writer,
            click.progressbar(length=total, file=sys.stderr) as bar,
        ):
            for batch in batched(rows, ROW_GROUP_SIZE):
                row_dicts = [row.model_dump(mode="python") for row in batch]
                table = pa.Table.from_pylist(row_dicts, schema=schema)
                writer.write_table(table)
                bar.update(len(batch))

        storage = storages["sponsored"]
        if storage.exists(storage_key):
            storage.delete(storage_key)

        with tmp_path.open("rb") as f:
            storage.save(storage_key, f)

    click.echo(f"Uploaded to storage key: {storage_key}", err=True)
