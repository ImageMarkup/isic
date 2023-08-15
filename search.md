# Notes on full-text search experimentation

## Postgres notes

Because we want different search weights, sorting by relevance, and multiple columns searched, a
simplistic GIN index is not sufficient to avoid full table scans, even for the Study and Collection
searches. The following `EXPLAIN` output happens even with the presence of ts-vector GIN indexes on
all relevant columns.

```python
In [33]: Image.objects.text_search('melanoma').explain()
EXPLAIN SELECT "core_image"."id",
       "core_image"."modified",
       "core_image"."created",
       "core_image"."accession_id",
       "core_image"."isic_id",
       "core_image"."creator_id",
       "core_image"."public",
       ts_rank(to_tsvector(COALESCE("core_image"."isic_id", '') || ' ' || COALESCE((("ingest_accession"."metadata" -> 'diagnosis'))::text, '')), plainto_tsquery('melanoma')) AS "search_rank",
       "ingest_accession"."id",
       "ingest_accession"."modified",
       "ingest_accession"."created",
       "ingest_accession"."creator_id",
       "ingest_accession"."girder_id",
       "ingest_accession"."zip_upload_id",
       "ingest_accession"."cohort_id",
       "ingest_accession"."original_blob",
       "ingest_accession"."original_blob_name",
       "ingest_accession"."original_blob_size",
       "ingest_accession"."blob",
       "ingest_accession"."blob_name",
       "ingest_accession"."blob_size",
       "ingest_accession"."width",
       "ingest_accession"."height",
       "ingest_accession"."status",
       "ingest_accession"."thumbnail_256",
       "ingest_accession"."thumbnail_256_size",
       "ingest_accession"."metadata",
       "ingest_accession"."unstructured_metadata"
  FROM "core_image"
 INNER JOIN "ingest_accession"
    ON ("core_image"."accession_id" = "ingest_accession"."id")
 WHERE ts_rank(to_tsvector(COALESCE("core_image"."isic_id", '') || ' ' || COALESCE((("ingest_accession"."metadata" -> 'diagnosis'))::text, '')), plainto_tsquery('melanoma')) > 0.0
 ORDER BY "search_rank" DESC

Execution time: 0.008215s [Database: default]
Out[33]: "Gather Merge  (cost=117918.35..123349.11 rows=47224 width=921)\n  Workers Planned: 1  ->  Sort  (cost=116918.34..117036.40 rows=47224 width=921)\n        Sort Key: (ts_rank(to_tsvector((((COALESCE(core_image.isic_id, ''::character varying))::text || ' '::text) || COALESCE(((ingest_accession.metadata -> 'diagnosis'::text))::text, ''::text))), plainto_tsquery('melanoma'::text))) DESC\n        ->  Parallel Hash Join  (cost=49319.08..94044.05 rows=47224 width=921)\n              Hash Cond: (core_image.accession_id = ingest_accession.id)\n              Join Filter: (ts_rank(to_tsvector((((COALESCE(core_image.isic_id, ''::character varying))::text || ' '::text) || COALESCE(((ingest_accession.metadata -> 'diagnosis'::text))::text, ''::text))), plainto_tsquery('melanoma'::text)) > '0'::double precision)\n              ->  Parallel Seq Scan on core_image  (cost=0.00..4153.72 rows=141672 width=50)\n              ->  Parallel Hash  (cost=34709.70..34709.70 rows=119870 width=867)\n                    ->  Parallel Seq Scan on ingest_accession  (cost=0.00..34709.70 rows=119870 width=867)\nJIT:\n  Functions: 12\n  Options: Inlining false, Optimization false, Expressions true, Deforming true"

In [35]: Collection.objects.text_search('melanoma').explain()
EXPLAIN SELECT "core_collection"."id",
       "core_collection"."created",
       "core_collection"."modified",
       "core_collection"."creator_id",
       "core_collection"."name",
       "core_collection"."description",
       "core_collection"."public",
       "core_collection"."pinned",
       "core_collection"."doi_id",
       "core_collection"."locked",
       ts_rank((setweight(to_tsvector(COALESCE("core_collection"."name", '')), 'A') || setweight(to_tsvector(COALESCE("core_collection"."description", '')), 'B')), plainto_tsquery('melanoma')) AS "search_rank"
  FROM "core_collection"
 WHERE ts_rank((setweight(to_tsvector(COALESCE("core_collection"."name", '')), 'A') || setweight(to_tsvector(COALESCE("core_collection"."description", '')), 'B')), plainto_tsquery('melanoma')) > 0.0
 ORDER BY "search_rank" DESC

Execution time: 0.003668s [Database: default]
Out[35]: 'Sort  (cost=121.71..121.81 rows=38 width=124)\n  Sort Key: (ts_rank((setweight(to_tsvector((COALESCE(name, \'\'::character varying))::text), \'A\'::"char") || setweight(to_tsvector(COALESCE(description, \'\'::text)), \'B\'::"char")), plainto_tsquery(\'melanoma\'::text))) DESC\n  ->  Seq Scan on core_collection  (cost=0.00..120.72 rows=38 width=124)\n        Filter: (ts_rank((setweight(to_tsvector((COALESCE(name, \'\'::character varying))::text), \'A\'::"char") || setweight(to_tsvector(COALESCE(description, \'\'::text)), \'B\'::"char")), plainto_tsquery(\'melanoma\'::text)) > \'0\'::double precision)'
```

These full table scans are completely fine on the Collection and Study tables due to their
cardinality, but require hundreds of ms to full-text search the Images/Accessions.

In the case of Collections and Studies, we could use a `GENERATED ALWAYS` derived column to
ensure the text search hits the index. However, in the case of Images, there is no way to take
advantage of an indexed full-text search without application-layer denormalization, since its
searched fields span multiple relations.

**Conclusion**: Given that:

* The cost of full-text search is dominated by Image search,
* We will require application-layer data duplication somewhere,
* We are already using ElasticSearch anyway,

if indexed full-text search is a must-have, we should probably leverage
ElasticSearch. However, if we don't care about a full table scan, this postgres approach affords us
a great deal of flexibility, power, and simplicity for minimal effort.

## ElasticSearch

...to be continued
