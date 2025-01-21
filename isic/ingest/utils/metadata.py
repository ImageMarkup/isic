from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
import csv
import itertools
from typing import Any

from django.forms.models import ModelForm
from isic_metadata.metadata import IGNORE_RCM_MODEL_CHECKS, MetadataBatch, MetadataRow
from pydantic import ValidationError as PydanticValidationError
from pydantic.main import BaseModel
from s3_file_field.widgets import S3FileInput

from isic.ingest.models import Accession, Cohort, MetadataFile


class MetadataForm(ModelForm):
    class Meta:
        model = MetadataFile
        fields = ["blob"]
        widgets = {"blob": S3FileInput(attrs={"accept": "text/csv"})}


class Problem(BaseModel):
    message: str
    context: list | None = None
    type: str | None = "error"


# A dictionary of (column name, error message) -> list of row indices with that error
ColumnRowErrors = dict[tuple[str, str], list[int]]


def validate_csv_format_and_filenames(rows: csv.DictReader, cohort: Cohort) -> list[Problem]:
    problems = []
    filenames = Counter()

    if not rows.fieldnames or "filename" not in rows.fieldnames:
        problems.append(Problem(message="Unable to find a filename column in CSV."))
        return problems

    filenames.update(row["filename"] for row in rows)

    if filenames and filenames.most_common(1)[0][1] > 1:
        problems.append(
            Problem(
                message="Duplicate filenames found.",
                context=[filename for filename, count in filenames.most_common() if count > 1],
            )
        )

    matching_accessions = set(
        Accession.objects.filter(cohort=cohort, original_blob_name__in=filenames.keys())
        .values_list("original_blob_name", flat=True)
        .iterator()
    )

    unknown_images = set(filenames.keys()) - matching_accessions
    if unknown_images:
        problems.append(
            Problem(
                message="Encountered unknown images in the CSV.",
                context=list(unknown_images),
                type="warning",
            )
        )

    return problems


def _validate_df_consistency(
    batch: Iterable[Mapping[str, Any]],
) -> tuple[ColumnRowErrors, list[Problem]]:
    column_error_rows: ColumnRowErrors = defaultdict(list)
    batch_problems: list[Problem] = []

    # since batch can be exhausted, keep track of all the batch level metadata rows
    # so we can validate them after exhausting the batch.
    batch_metadata_rows: list[MetadataRow] = []

    for i, row in enumerate(batch, start=2):
        try:
            MetadataRow.model_validate(row)
        except PydanticValidationError as e:
            for error in e.errors():
                column = error["loc"][0] if error["loc"] else ""
                column_error_rows[(str(column), error["msg"])].append(i)

        if row.get("patient_id") or row.get("lesion_id") or row.get("rcm_case_id"):
            try:
                batch_metadata_row = MetadataRow(
                    patient_id=row.get("patient_id"),
                    lesion_id=row.get("lesion_id"),
                    rcm_case_id=row.get("rcm_case_id"),
                    # image_type is necessary for the batch check because RCM can only have
                    # at most one macroscopic image.
                    image_type=row.get("image_type"),
                    # see the documentation for the IGNORE_RCM_MODEL_CHECKS setting
                    **{IGNORE_RCM_MODEL_CHECKS: True},
                )
            except PydanticValidationError:
                # it's possible that even the narrow subset of fields we're trying to validate for
                # batch checks can't be validated at a row level. this is because image_type is an
                # enum. only validate as much of the batch as we can. this isn't ideal but the
                # alternative is to make MetadataRow more complicated and only optionally
                # validate the rules regarding rcm/image_type.
                ...
            else:
                batch_metadata_rows.append(batch_metadata_row)

    # validate the metadata as a "batch". this is for all checks that span rows. since this
    # currently only applies to patient/lesion/rcm checks, we can sparsely populate the MetadataRow
    # objects to save on memory.
    try:
        MetadataBatch(items=batch_metadata_rows)
    except PydanticValidationError as e:
        for error in e.errors():
            examples = error["ctx"]["examples"] if "ctx" in error else []
            batch_problems.append(Problem(message=error["msg"], context=examples))

    # defaultdict doesn't work with django templates, see https://stackoverflow.com/a/12842716
    return dict(column_error_rows), batch_problems


def validate_internal_consistency(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[ColumnRowErrors, list[Problem]]:
    return _validate_df_consistency(rows)


def validate_archive_consistency(  # noqa: C901
    rows: csv.DictReader, cohort: Cohort
) -> tuple[ColumnRowErrors, list[Problem]]:
    """
    Validate that a CSV is consistent with the existing cohort metadata.

    This merges the existing cohort metadata with the proposed df and validates the merged
    metadata. This allows for cross column checks e.g. an existing benign accession against
    a df with diagnosis=melanoma. It also enables cross row checks, such as verifying that
    a lesion doesn't belong to more than one patient.
    """

    def cohort_df_merged_metadata_rows() -> Iterable[dict[str, Any]]:
        """
        Yield the merged metadata rows for the cohort and df.

        The merged metadata rows are generated by iterating over the cohort accessions and
        yielding the metadata for each accession. It merges if necessary and then yields the
        merged result, remembering to omit it when yielding from the remaining rows in the csv.
        """
        accessions = cohort.accessions.values(
            "original_blob_name",
            *[
                f"{field.relation_name}__{field.internal_id_name}"
                for field in Accession.remapped_internal_fields
            ],
            *Accession.metadata_keys(),
        )

        def accession_values_to_metadata_dict(accession_values: dict[str, Any]) -> dict[str, Any]:
            """
            Return the relevant metadata values from the Accession.values dict.

            This is sort of like Accession.metadata but for a single accession retrieved
            as a dict.
            """
            if "original_blob_name" in accession_values:
                del accession_values["original_blob_name"]

            for field in Accession.remapped_internal_fields:
                if accession_values[f"{field.relation_name}__{field.internal_id_name}"]:
                    accession_values[field.csv_field_name] = accession_values[
                        f"{field.relation_name}__{field.internal_id_name}"
                    ]
                    del accession_values[f"{field.relation_name}__{field.internal_id_name}"]

            diagnosis_fields = [
                f"diagnosis_{i}" for i in range(1, 6) if f"diagnosis_{i}" in accession_values
            ]
            if any(accession_values[field] for field in diagnosis_fields):
                accession_values["diagnosis"] = ":".join(
                    accession_values[field] for field in diagnosis_fields if accession_values[field]
                )

            return {k: v for (k, v) in accession_values.items() if v is not None}

        yielded_filenames: set[str] = set()

        for batch in itertools.batched(rows, 5_000):
            accessions_batch = accessions.filter(
                original_blob_name__in=[row["filename"] for row in batch]
            )
            accessions_by_filename = {
                a["original_blob_name"]: accession_values_to_metadata_dict(a)
                for a in accessions_batch
            }

            for row in batch:
                existing = accessions_by_filename[row["filename"]]

                if existing:
                    yield existing | row
                    yielded_filenames.add(row["filename"])
                else:
                    yield row

        for row in accessions.exclude(original_blob_name__in=yielded_filenames).iterator():
            yield accession_values_to_metadata_dict(row)

    return _validate_df_consistency(cohort_df_merged_metadata_rows())
