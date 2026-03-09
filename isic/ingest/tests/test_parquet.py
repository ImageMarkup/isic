from decimal import Decimal
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic_to_pyarrow import get_pyarrow_schema
import pytest

from isic.ingest.utils.parquet import (
    EXCLUDED_FIELDS,
    FIELD_ORDER,
    ParquetMetadataRow,
    build_parquet_schema,
)


def test_field_order_covers_all_schema_fields():
    schema = get_pyarrow_schema(ParquetMetadataRow, exclude_fields=True)
    all_field_names = {f.name for f in schema}
    expected_fields = all_field_names - set(EXCLUDED_FIELDS)

    assert set(FIELD_ORDER) == expected_fields


def test_build_parquet_schema_field_order():
    schema = build_parquet_schema()
    assert [f.name for f in schema] == FIELD_ORDER


def test_build_parquet_schema_with_metadata():
    schema = build_parquet_schema(
        parquet_metadata={"snapshot_timestamp": "2026-01-01T00:00:00+00:00"}
    )
    assert schema.metadata[b"snapshot_timestamp"] == b"2026-01-01T00:00:00+00:00"


def test_parquet_metadata_row_roundtrip_through_parquet():
    row = ParquetMetadataRow(
        isic_id="ISIC_0000001",
        attribution="Test Attribution",
        copyright_license="CC-0",
        sex="male",
        age_approx=50,
        clin_size_long_diam_mm=Decimal("3.14"),
        melanocytic=True,
    )

    schema = build_parquet_schema()
    row_dicts = [row.model_dump(mode="python")]
    table = pa.Table.from_pylist(row_dicts, schema=schema)

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        pq.write_table(table, tmp.name)
        result = pq.read_table(tmp.name)

    assert result.num_rows == 1
    result_dict = result.to_pydict()
    assert result_dict["isic_id"] == ["ISIC_0000001"]
    assert result_dict["attribution"] == ["Test Attribution"]
    assert result_dict["copyright_license"] == ["CC-0"]
    assert result_dict["sex"] == ["male"]
    assert result_dict["age_approx"] == [50]
    assert result_dict["clin_size_long_diam_mm"] == [Decimal("3.14")]
    assert result_dict["melanocytic"] == [True]


@pytest.mark.django_db
def test_parquet_metadata_row_from_image(image_factory, accession_factory):
    accession = accession_factory(
        public=True,
        attribution="Test Hospital",
        sex="female",
        age=55,
        short_diagnosis="melanoma",
        short_anatom_site="scalp",
    )
    image = image_factory(accession=accession, public=True)

    row = ParquetMetadataRow(
        isic_id=image.isic_id,
        attribution=image.accession.attribution,
        copyright_license=image.accession.copyright_license,
        **image.metadata,
    )

    schema = build_parquet_schema()
    row_dicts = [row.model_dump(mode="python")]
    table = pa.Table.from_pylist(row_dicts, schema=schema)

    assert table.num_rows == 1
    result = table.to_pydict()
    assert result["isic_id"] == [image.isic_id]
    assert result["sex"] == ["female"]
    assert result["age_approx"] == [55]
    assert result["anatom_site_1"][0] == "Head and neck"
    assert result["diagnosis_1"][0] == "Malignant"
