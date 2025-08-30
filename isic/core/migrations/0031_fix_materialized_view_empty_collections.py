from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0030_draftdoi_draftdoirelatedidentifier_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
DROP MATERIALIZED VIEW IF EXISTS materialized_collection_counts;

CREATE MATERIALIZED VIEW materialized_collection_counts AS
SELECT
    c.id AS id,
    COUNT(DISTINCT ingest_accession.lesion_id) AS lesion_count,
    COUNT(DISTINCT ingest_accession.patient_id) AS patient_count,
    COUNT(ci.image_id) AS image_count
FROM core_collection AS c
LEFT JOIN core_collectionimage AS ci ON c.id = ci.collection_id
LEFT JOIN core_image ON ci.image_id = core_image.id
LEFT JOIN ingest_accession ON core_image.accession_id = ingest_accession.id
GROUP BY c.id;

-- a unique index is necessary to be able to refresh the materialized view concurrently
CREATE UNIQUE INDEX IF NOT EXISTS materialized_collection_counts_unique_id
ON materialized_collection_counts (id);
            """,
            elidable=False,
        ),
    ]
