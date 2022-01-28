import functools
import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import needs_object_permission
from isic.ingest.filters import AccessionFilter
from isic.ingest.forms import SingleAccessionUploadForm
from isic.ingest.models import Accession, Cohort, ZipUpload
from isic.ingest.models.accession import ACCESSION_CHECKS
from isic.ingest.tasks import extract_zip_task, process_accession_task, publish_cohort_task


def make_breadcrumbs(cohort: Cohort | None = None) -> list:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret


class ZipForm(ModelForm):
    class Meta:
        model = ZipUpload
        fields = ['blob']


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_single_accession(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    Form = functools.partial(  # noqa: N806
        SingleAccessionUploadForm, user=request.user, cohort=cohort
    )
    if request.method == 'POST':
        form = Form(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.cohort = cohort
            form.instance.blob_name = os.path.basename(form.instance.original_blob.name)
            form.save()
            process_accession_task.delay(form.instance.pk)
            messages.add_message(
                request,
                messages.SUCCESS,
                f'The following accession has been uploaded: {form.instance.blob_name}',
            )
            return HttpResponseRedirect(
                reverse('upload/cohort-files', args=[form.instance.cohort.pk])
            )
    else:
        form = Form()

    return render(request, 'ingest/upload_zip_or_accession.html', {'form': form})


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_zip(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    if request.method == 'POST':
        form = ZipForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = os.path.basename(form.instance.blob.name)
            form.instance.cohort = cohort
            form.save(commit=True)
            extract_zip_task.delay(form.instance.pk)
            return HttpResponseRedirect(reverse('upload/cohort-files', args=[cohort.pk]))
    else:
        form = ZipForm()

    return render(request, 'ingest/upload_zip_or_accession.html', {'form': form})


@staff_member_required
def cohort_detail(request, pk):
    cohort = get_object_or_404(Cohort.objects.select_related('creator'), pk=pk)

    return render(
        request,
        'ingest/cohort_detail.html',
        {
            'cohort': cohort,
            'check_counts': Accession.check_counts(cohort),
            'checks': ACCESSION_CHECKS,
            'breadcrumbs': make_breadcrumbs(cohort),
            'review_urls': {
                'phi_check': 'cohort-review-quality-and-phi',
                'quality_check': 'cohort-review-quality-and-phi',
                'diagnosis_check': 'cohort-review-diagnosis',
                'duplicate_check': 'cohort-review-duplicate',
                'lesion_check': 'cohort-review-lesion',
            },
            'check_nicenames': {
                'phi_check': 'PHI',
                'quality_check': 'Quality',
                'diagnosis_check': 'Diagnosis',
                'duplicate_check': 'Duplicate',
                'lesion_check': 'Lesion',
            },
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


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'pk'))
def cohort_browser(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)
    filter = AccessionFilter(request.GET, queryset=cohort.accessions.all())
    paginator = Paginator(filter.qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/cohort_browser.html',
        {
            'cohort': cohort,
            'accessions': page,
            'filter': filter,
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Browse Accessions']],
        },
    )


@staff_member_required  # TODO: who gets to publish a cohort? anyone who can view it?
@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'pk'))
def publish_cohort(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)

    if request.method == 'POST':
        public = False
        if 'public' in request.POST:
            public = True
        elif 'private' in request.POST:
            public = False
        else:
            raise Exception

        publish_cohort_task.delay(cohort.pk, public=public)
        messages.add_message(
            request,
            messages.SUCCESS,
            f'Publishing {intcomma(cohort.publishable_accessions().count())} images. This may take several minutes.',  # noqa: E501
        )
        return HttpResponseRedirect(reverse('cohort-detail', args=[cohort.pk]))
    else:
        ctx = {
            'cohort': cohort,
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Publish Cohort']],
            'num_accessions': cohort.accessions.count(),
            'num_published': cohort.published_accessions().count(),
            'num_publishable': cohort.publishable_accessions().count(),
            'num_rejected': cohort.rejected_accessions().count(),
            'num_pending_or_failed': cohort.pending_or_failed_accessions().count(),
        }

    ctx['num_unpublishable'] = ctx['num_accessions'] - ctx['num_publishable']

    return render(request, 'ingest/cohort_publish.html', ctx)
