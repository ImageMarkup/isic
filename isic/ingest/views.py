from collections import defaultdict
from typing import Optional

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
import numpy as np
import pandas as pd
from pydantic.main import BaseModel

from isic.ingest.filters import AccessionFilter
from isic.ingest.forms import CohortForm
from isic.ingest.models import Accession, Cohort, DistinctnessMeasure, MetadataFile, Zip
from isic.ingest.tasks import apply_metadata as apply_metadata_task, extract_zip
from isic.ingest.validators import MetadataRow


class ZipForm(ModelForm):
    class Meta:
        model = Zip
        fields = ['blob']


@staff_member_required
def zip_create(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )
    if request.method == 'POST':
        form = ZipForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = form.instance.blob.name
            form.instance.cohort = cohort
            form.save(commit=True)
            extract_zip.delay(form.instance.id)
            return HttpResponseRedirect(reverse('cohort-detail', args=[cohort.pk]))
    else:
        form = ZipForm()

    return render(request, 'ingest/zip_create.html', {'form': form})


@staff_member_required
def cohort_list(request):
    cohorts = Cohort.objects.all().order_by('-created')
    return render(
        request,
        'ingest/cohort_list.html',
        {
            'cohorts': cohorts,
        },
    )


@staff_member_required
def reset_metadata(request, cohort_pk):
    # TODO: GET request to mutate?
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    Accession.objects.filter(upload__cohort=cohort).update(metadata={})
    messages.info(request, 'Metadata has been reset.')
    return HttpResponseRedirect(reverse('cohort-detail', args=[cohort_pk]))


@staff_member_required
def cohort_detail(request, pk):
    cohort = get_object_or_404(
        Cohort,
        pk=pk,
    )
    accession_qs = Accession.objects.filter(upload__cohort=cohort).order_by('created')
    filter_ = AccessionFilter(request.GET, queryset=accession_qs, cohort=cohort)
    num_duplicates = accession_qs.filter(
        distinctnessmeasure__checksum__in=DistinctnessMeasure.objects.values('checksum')
        .annotate(is_duplicate=Count('checksum'))
        .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
        .values('checksum')
    ).count()
    num_unique_lesions = (
        Accession.objects.filter(metadata__lesion_id__isnull=False, upload__cohort=cohort)
        .values('metadata__lesion_id')
        .distinct()
        .count()
    )
    num_skipped_accessions = accession_qs.filter(status=Accession.Status.SKIPPED).count()

    paginator = Paginator(filter_.qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'ingest/cohort_detail.html',
        {
            'cohort': cohort,
            'page_obj': page_obj,
            'filter': filter_,
            'num_duplicates': num_duplicates,
            'num_unique_lesions': num_unique_lesions,
            'num_skipped_accessions': num_skipped_accessions,
            'total_accessions': filter_.qs.count(),
        },
    )


class MetadataForm(ModelForm):
    class Meta:
        model = MetadataFile
        fields = ['blob']


class Problem(BaseModel):
    message: Optional[str]
    context: Optional[list]
    type: Optional[str] = 'error'


def validate_csv_format_and_filenames(df, cohort):
    problems = []

    # TODO: duplicate columns

    if 'filename' not in df.columns:
        problems.append(Problem(message='Unable to find a filename column in CSV.'))
        return problems

    matching_accessions = Accession.objects.filter(
        upload__cohort=cohort, blob_name__in=df['filename']
    ).values_list('blob_name', 'metadata')

    duplicate_filenames = df[df['filename'].duplicated()].filename.values
    if duplicate_filenames.size:
        problems.append(
            Problem(message='Duplicate filenames found.', context=list(duplicate_filenames))
        )

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
        upload__cohort=cohort, blob_name__in=df['filename']
    ).values_list('blob_name', 'metadata')
    # TODO: easier way to do this?
    accessions_dict = {x[0]: x[1] for x in accessions}

    for i, (_, row) in enumerate(df.iterrows(), start=2):
        existing = accessions_dict[row['filename']]
        row = {**existing, **{k: v for k, v in row.items() if v is not None}}

        try:
            MetadataRow.parse_obj(row)
        except Exception as e:
            for error in e.errors():
                column = error['loc'][0]

                column_problems[(column, error['msg'])].append(i)

    # TODO: defaultdict doesn't work in django templates?
    return dict(column_problems)


@staff_member_required
def apply_metadata(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )

    checkpoints = {
        1: {
            'title': 'Filename checks',
            'run': False,
            'problems': [],
        },
        2: {
            'title': 'Internal consistency',
            'run': False,
            'problems': [],
        },
        3: {
            'title': 'Archive consistency',
            'run': False,
            'problems': [],
        },
    }

    if request.method == 'POST':
        form = MetadataForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.cohort = cohort
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = form.instance.blob.name
            form.instance.save()
            with form.instance.blob.open() as csv:
                df = pd.read_csv(csv, header=0)

            checkpoints[1]['problems'] = validate_csv_format_and_filenames(df, cohort)
            checkpoints[1]['run'] = True

            # pydantic expects None for the absence of a value, not NaN
            df = df.replace({np.nan: None})

            if not checkpoints[1]['problems']:
                checkpoints[2]['problems'] = validate_internal_consistency(df)
                checkpoints[2]['run'] = True

                if not checkpoints[2]['problems']:
                    checkpoints[3]['problems'] = validate_archive_consistency(df, cohort)
                    checkpoints[3]['run'] = True

                    if not checkpoints[3]['problems']:
                        apply_metadata_task.delay(form.instance.id)
                        messages.info(request, 'Metadata is being applied.')

    else:
        form = MetadataForm()

    return render(
        request,
        'ingest/apply_metadata.html',
        {'cohort': cohort, 'form': form, 'checkpoint': checkpoints},
    )


@staff_member_required
def review_duplicates(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )
    duplicate_checksums = (
        DistinctnessMeasure.objects.filter(
            accession__upload__cohort=cohort,
            checksum__in=DistinctnessMeasure.objects.values('checksum')
            .annotate(is_duplicate=Count('checksum'))
            .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
            .values_list('checksum', flat=True),
        )
        .order_by('checksum')
        .distinct('checksum')
        .values_list('checksum', flat=True)
    )

    paginator = Paginator(duplicate_checksums, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    related_accessions: dict[str, list] = defaultdict(list)
    for accession in Accession.objects.select_related('distinctnessmeasure').filter(
        upload__cohort=cohort, distinctnessmeasure__checksum__in=duplicate_checksums
    ):
        related_accessions[accession.distinctnessmeasure.checksum].append(accession)

    return render(
        request,
        'ingest/review_duplicates.html',
        {'cohort': cohort, 'page_obj': page_obj, 'related_accessions': related_accessions},
    )


@staff_member_required
def review_skipped_accessions(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )
    accessions = Accession.objects.filter(
        upload__cohort=cohort, status=Accession.Status.SKIPPED
    ).order_by('created')

    paginator = Paginator(accessions, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'ingest/review_skipped_accessions.html',
        {'cohort': cohort, 'page_obj': page_obj, 'total_accessions': accessions.count()},
    )


@staff_member_required
def review_lesion_groups(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )
    lesion_ids = (
        Accession.objects.filter(upload__cohort=cohort, metadata__lesion_id__isnull=False)
        .order_by('metadata__lesion_id')
        .distinct('metadata__lesion_id')
        .values_list('metadata__lesion_id', flat=True)
    )

    paginator = Paginator(lesion_ids, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    related_accessions: dict[str, list] = defaultdict(list)
    for accession in Accession.objects.filter(
        upload__cohort=cohort, metadata__lesion_id__in=lesion_ids
    ):
        related_accessions[accession.metadata['lesion_id']].append(accession)

    return render(
        request,
        'ingest/review_lesion_groups.html',
        {'cohort': cohort, 'page_obj': page_obj, 'related_accessions': related_accessions},
    )


@staff_member_required
def cohort_create(request):
    if request.method == 'POST':
        form = CohortForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.save(commit=True)
            return HttpResponseRedirect(reverse('cohort-detail', args=[form.instance.pk]))
    else:
        form = CohortForm()

    return render(request, 'ingest/cohort_create.html', {'form': form})
