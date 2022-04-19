import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from django.utils.safestring import mark_safe
from s3_file_field.widgets import S3FileInput

from isic.core.permissions import needs_object_permission
from isic.core.services.collection import collection_create
from isic.ingest.forms import SingleAccessionUploadForm
from isic.ingest.models import Cohort, ZipUpload
from isic.ingest.service import accession_create
from isic.ingest.tasks import extract_zip_task, publish_cohort_task


def make_breadcrumbs(cohort: Cohort | None = None) -> list:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret


class ZipForm(ModelForm):
    class Meta:
        model = ZipUpload
        fields = ['blob']
        widgets = {'blob': S3FileInput(attrs={'accept': 'application/zip'})}


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_single_accession(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == 'POST':
        form = SingleAccessionUploadForm(request.POST)

        if form.is_valid():
            accession_create(
                creator=request.user,
                cohort=cohort,
                original_blob=form.cleaned_data['original_blob'],
                blob_name=os.path.basename(form.cleaned_data['original_blob'].name),
            )
            messages.add_message(
                request,
                messages.SUCCESS,
                mark_safe(f'Accession uploaded.'),
            )
            return HttpResponseRedirect(reverse('upload/cohort-files', args=[cohort.pk]))
    else:
        form = SingleAccessionUploadForm()

    return render(request, 'ingest/upload_zip_or_accession.html', {'form': form})


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_zip(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == 'POST':
        form = ZipForm(request.POST, request.FILES)
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
    paginator = Paginator(cohort.accessions.ingested(), 50)
    accessions = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/cohort_detail.html',
        {
            'cohort': cohort,
            'accessions': accessions,
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

        if not cohort.collection:
            cohort.collection = collection_create(
                creator=request.user,
                name=f'Publish of {cohort.name}',
                description='',
                public=False,
            )
            cohort.save(update_fields=['collection'])

        publish_cohort_task.delay(cohort.pk, request.user.pk, public=public)
        messages.add_message(
            request,
            messages.SUCCESS,
            f'Publishing {intcomma(cohort.accessions.publishable().count())} images. This may take several minutes.',  # noqa: E501
        )
        return HttpResponseRedirect(reverse('cohort-detail', args=[cohort.pk]))
    else:
        ctx = {
            'cohort': cohort,
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Publish Cohort']],
            'num_accessions': cohort.accessions.count(),
            'num_published': cohort.accessions.published().count(),
            'num_publishable': cohort.accessions.publishable().count(),
            'num_rejected': cohort.accessions.rejected().count(),
            'num_pending': cohort.accessions.ingesting().count(),
            'num_uningested': cohort.accessions.uningested().count(),
        }

    ctx['num_unpublishable'] = ctx['num_accessions'] - ctx['num_publishable']

    return render(request, 'ingest/cohort_publish.html', ctx)
