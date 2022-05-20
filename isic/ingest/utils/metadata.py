from collections import defaultdict

from django.forms.models import ModelForm
from isic_metadata.metadata import MetadataRow
import pandas as pd
from pydantic.main import BaseModel
from s3_file_field.widgets import S3FileInput

from isic.ingest.models import Accession, MetadataFile


class MetadataForm(ModelForm):
    class Meta:
        model = MetadataFile
        fields = ['blob']
        widgets = {'blob': S3FileInput(attrs={'accept': 'text/csv'})}


class Problem(BaseModel):
    message: str | None
    context: list | None
    type: str | None = 'error'


def validate_csv_format_and_filenames(df, cohort):
    problems = []

    # TODO: duplicate columns

    if 'filename' not in df.columns:
        problems.append(Problem(message='Unable to find a filename column in CSV.'))
        return problems

    duplicate_filenames = df[df['filename'].duplicated()].filename.values
    if duplicate_filenames.size:
        problems.append(
            Problem(message='Duplicate filenames found.', context=list(duplicate_filenames))
        )

    matching_accessions = Accession.objects.filter(
        cohort=cohort, original_blob_name__in=df['filename']
    ).values_list('original_blob_name', 'metadata')

    existing_df = pd.DataFrame((x[0] for x in matching_accessions), columns=['filename'])
    unknown_images = set(df.filename.values) - set(existing_df.filename.values)
    if unknown_images:
        problems.append(
            Problem(
                message='Encountered unknown images in the CSV.',
                context=list(unknown_images),
                type='warning',
            )
        )

    return problems


def validate_internal_consistency(df):
    # keyed by column, message
    column_problems: dict[tuple[str, str], list[int]] = defaultdict(list)

    for i, (_, row) in enumerate(df.iterrows(), start=2):
        try:
            MetadataRow.parse_obj(row)
        except Exception as e:
            for error in e.errors():
                column = error['loc'][0]
                column_problems[(column, error['msg'])].append(i)

    # TODO: defaultdict doesn't work in django templates?
    return dict(column_problems)


def validate_archive_consistency(df, cohort):
    # keyed by column, message
    column_problems: dict[tuple[str, str], list[int]] = defaultdict(list)
    accessions = Accession.objects.filter(
        cohort=cohort, original_blob_name__in=df['filename']
    ).values_list('original_blob_name', 'metadata')
    # TODO: easier way to do this?
    accessions_dict = {x[0]: x[1] for x in accessions}

    for i, (_, row) in enumerate(df.iterrows(), start=2):
        existing = accessions_dict[row['filename']]
        row = existing | {k: v for k, v in row.items() if v is not None}

        try:
            MetadataRow.parse_obj(row)
        except Exception as e:
            for error in e.errors():
                column = error['loc'][0]

                column_problems[(column, error['msg'])].append(i)

    # TODO: defaultdict doesn't work in django templates?
    return dict(column_problems)
