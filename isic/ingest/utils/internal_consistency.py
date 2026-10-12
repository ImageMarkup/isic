"""
Metadata checks that need nothing but the CSV rows.

The metadata validator page also runs this module in the browser with Pyodide, so it can only
import the standard library, isic_metadata, and pydantic.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from isic_metadata.metadata import MetadataBatch, MetadataRow
from pydantic import ValidationError as PydanticValidationError
from pydantic.main import BaseModel


class Problem(BaseModel):
    message: str
    context: list | None = None
    type: str | None = "error"


# A dictionary of (column name, error message) -> list of row indices with that error
ColumnRowErrors = dict[tuple[str, str], list[int]]


def validate_internal_consistency(
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
                batch_metadata_row = MetadataRow.model_validate(
                    {
                        "patient_id": row.get("patient_id"),
                        "lesion_id": row.get("lesion_id"),
                        "rcm_case_id": row.get("rcm_case_id"),
                        # image_type is necessary for the batch check because RCM can only have
                        # at most one macroscopic image.
                        "image_type": row.get("image_type"),
                    },
                    context={"ignore_rcm_model_checks": True},
                )
            except PydanticValidationError:
                # it's possible that even the narrow subset of fields we're trying to validate for
                # batch checks can't be validated at a row level. this is because image_type is an
                # enum. only validate as much of the batch as we can. this isn't ideal but the
                # alternative is to make MetadataRow more complicated and only optionally
                # validate the rules regarding rcm/image_type.
                pass
            else:
                batch_metadata_rows.append(batch_metadata_row)

    # validate the metadata as a "batch". this is for all checks that span rows. since this
    # currently only applies to patient/lesion/rcm checks, we can sparsely populate the MetadataRow
    # objects to save on memory.
    try:
        MetadataBatch.model_validate(
            {"items": batch_metadata_rows},
            context={"ignore_rcm_model_checks": True},
        )
    except PydanticValidationError as e:
        for error in e.errors():
            examples = error["ctx"]["examples"] if "ctx" in error else []
            batch_problems.append(Problem(message=error["msg"], context=examples))

    # defaultdict doesn't work with django templates, see https://stackoverflow.com/a/12842716
    return dict(column_error_rows), batch_problems
