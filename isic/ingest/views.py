from collections import Counter, defaultdict
from itertools import groupby
from typing import Optional

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
from isic.ingest.tasks import extract_zip
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
def cohort_detail(request, pk):
    cohort = get_object_or_404(
        Cohort,
        pk=pk,
    )
    accession_qs = Accession.objects.filter(upload__cohort=cohort).order_by('created')
    filter_ = AccessionFilter(request.GET, queryset=accession_qs)
    num_duplicates = accession_qs.filter(
        distinctnessmeasure__checksum__in=DistinctnessMeasure.objects.values('checksum')
        .annotate(is_duplicate=Count('checksum'))
        .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
        .values('checksum')
    ).count()
    num_duplicate_filenames = accession_qs.filter(
        blob_name__in=Accession.objects.values('blob_name')
        .annotate(is_duplicate=Count('blob_name'))
        .filter(upload__cohort=cohort, is_duplicate__gt=1)
        .values('blob_name')
    ).count()

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
            'num_duplicate_filenames': num_duplicate_filenames,
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

    if 'filename' not in df.columns:
        problems.append(Problem(message='Unable to find a filename column in CSV.'))
        return problems

    # todo: upload__cohort=cohort,
    matching_accessions = Accession.objects.filter(
        upload__cohort=cohort, blob_name__in=df['filename']
    ).values_list('blob_name', 'metadata')

    duplicate_filenames = df[df['filename'].duplicated()].filename.values
    if duplicate_filenames.size:
        problems.append(
            Problem(message='Duplicate filenames found.', context=list(duplicate_filenames))
        )

    multiple_accessions = Counter(x[0] for x in matching_accessions)
    duplicate_accessions = [k for k, count in multiple_accessions.items() if count > 1]
    if duplicate_accessions:
        problems.append(
            Problem(
                message='These images matched more than 1 accession.', context=duplicate_accessions
            )
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
        row = {**existing, **row}

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
    duplicates = (
        Accession.objects.filter(upload__cohort=cohort)
        .select_related('distinctnessmeasure')
        .order_by('distinctnessmeasure__checksum')  # ordering by checksum is necessary for groupby
        .filter(
            distinctnessmeasure__checksum__in=DistinctnessMeasure.objects.values('checksum')
            .annotate(is_duplicate=Count('checksum'))
            .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
            .values('checksum')
        )
    )

    # TODO: investigate regroup template tag
    # TODO: if performance becomes an issue (too many duplicates), look into
    # windowing functions with postgres
    duplicate_groups = []
    for _, accession in groupby(duplicates, key=lambda a: a.distinctnessmeasure.checksum):
        duplicate_groups.append(list(accession))

    return render(
        request,
        'ingest/review_duplicates.html',
        {'cohort': cohort, 'duplicate_groups': duplicate_groups},
    )


@staff_member_required
def review_duplicate_filenames(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort,
        pk=cohort_pk,
    )
    duplicates = (
        Accession.objects.filter(upload__cohort=cohort)
        .order_by('created')
        .filter(
            blob_name__in=Accession.objects.values('blob_name')
            .annotate(is_duplicate=Count('blob_name'))
            .filter(upload__cohort=cohort, is_duplicate__gt=1)
            .values('blob_name')
        )
    )

    # TODO: investigate regroup template tag
    # TODO: if performance becomes an issue (too many duplicates), look into
    # windowing functions with postgres
    duplicate_groups = []
    for _, accession in groupby(duplicates, key=lambda a: a.blob_name):
        duplicate_groups.append(list(accession))

    return render(
        request,
        'ingest/review_duplicate_filenames.html',
        {'cohort': cohort, 'duplicate_groups': duplicate_groups},
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
