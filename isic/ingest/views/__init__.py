import os

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.ingest.models import Accession, AccessionStatus, Cohort, DistinctnessMeasure, Zip
from isic.ingest.tasks import extract_zip
from isic.ingest.utils import make_breadcrumbs, staff_or_owner_filter

from .metadata import *  # noqa
from .review_apps import *  # noqa
from .upload import *  # noqa


class ZipForm(ModelForm):
    class Meta:
        model = Zip
        fields = ['blob']


@login_required
def zip_create(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort.objects.filter(**staff_or_owner_filter(request.user, 'contributor__owners')),
        pk=cohort_pk,
    )
    if request.method == 'POST':
        form = ZipForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = os.path.basename(form.instance.blob.name)
            form.instance.cohort = cohort
            form.save(commit=True)
            extract_zip.delay(form.instance.pk)
            return HttpResponseRedirect(reverse('upload/cohort-files', args=[cohort.pk]))
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
    num_skipped_accessions = accession_qs.filter(status=AccessionStatus.SKIPPED).count()

    return render(
        request,
        'ingest/cohort_detail.html',
        {
            'cohort': cohort,
            'num_duplicates': num_duplicates,
            'num_unique_lesions': num_unique_lesions,
            'num_skipped_accessions': num_skipped_accessions,
            'total_accessions': accession_qs.count(),
            'check_counts': Accession.check_counts(cohort),
            'checks': Accession.checks(),
            'breadcrumbs': make_breadcrumbs(cohort),
        },
    )


@staff_member_required
def ingest_review(request):
    cohorts = Cohort.objects.select_related('contributor', 'creator').order_by('-created')
    paginator = Paginator(cohorts, 10)
    cohorts_page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/ingest_review.html',
        {'cohorts': cohorts_page, 'num_cohorts': paginator.count, 'paginator': paginator},
    )
