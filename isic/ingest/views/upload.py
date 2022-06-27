import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query import Prefetch
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from django.utils.safestring import mark_safe
from pydantic import ValidationError as MetadataValidationError
from s3_file_field.widgets import S3FileInput

from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.forms import CohortForm, ContributorForm, SingleAccessionUploadForm
from isic.ingest.models import Cohort, Contributor, MetadataFile, ZipUpload
from isic.ingest.services.accession import accession_create
from isic.ingest.tasks import extract_zip_task


class ZipForm(ModelForm):
    class Meta:
        model = ZipUpload
        fields = ['blob']
        widgets = {'blob': S3FileInput(attrs={'accept': 'application/zip'})}


@login_required
def select_or_create_contributor(request):
    ctx = {'contributors': get_visible_objects(request.user, 'ingest.view_contributor')}
    if ctx['contributors'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-contributor'))

    return render(request, 'ingest/contributor_select_or_create.html', ctx)


@needs_object_permission('ingest.view_contributor', (Contributor, 'pk', 'contributor_pk'))
def select_or_create_cohort(request, contributor_pk):
    contributor = Contributor.objects.get(pk=contributor_pk)
    ctx = {
        'cohorts': contributor.cohorts.order_by('-created'),
        'contributor_pk': contributor_pk,
    }
    if ctx['cohorts'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-cohort', args=[contributor_pk]))

    return render(request, 'ingest/cohort_select_or_create.html', ctx)


@needs_object_permission('ingest.add_contributor')
def upload_contributor_create(request):
    if request.method == 'POST':
        form = ContributorForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.save(commit=True)
            # The instance must be saved before ManyToMany relationships can be added
            form.instance.owners.add(request.user)
            return HttpResponseRedirect(reverse('upload/create-cohort', args=[form.instance.pk]))
    else:
        form = ContributorForm()

    return render(request, 'ingest/contributor_create.html', {'form': form})


@needs_object_permission('ingest.add_cohort', (Contributor, 'pk', 'contributor_pk'))
def upload_cohort_create(request, contributor_pk):
    contributor: Contributor = get_object_or_404(Contributor, pk=contributor_pk)

    if request.method == 'POST':
        form = CohortForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.contributor = contributor
            form.save(commit=True)
            return HttpResponseRedirect(reverse('upload/cohort-files', args=[form.instance.pk]))
    else:
        form = CohortForm(
            initial={
                'contributor': contributor.pk,
                'copyright_license': contributor.default_copyright_license,
                'attribution': contributor.default_attribution,
            }
        )

    return render(request, 'ingest/cohort_edit_or_create.html', {'form': form, 'creating': True})


@needs_object_permission('ingest.edit_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_cohort_edit(request, cohort_pk):
    cohort: Cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == 'POST':
        form = CohortForm(request.POST, instance=cohort)
        if form.is_valid():
            form.instance.creator = cohort.creator
            form.instance.contributor = cohort.contributor
            form.save(commit=True)
            return HttpResponseRedirect(reverse('cohort-detail', args=[form.instance.pk]))
    else:
        form = CohortForm(instance=cohort)

    return render(request, 'ingest/cohort_edit_or_create.html', {'form': form, 'creating': False})


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'pk'))
def cohort_files(request, pk):
    cohort = get_object_or_404(
        Cohort.objects.prefetch_related(
            Prefetch('metadata_files', queryset=MetadataFile.objects.order_by('-created'))
        ).prefetch_related('zip_uploads'),
        pk=pk,
    )
    return render(
        request,
        'ingest/cohort_files.html',
        {
            'cohort': cohort,
        },
    )


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def upload_single_accession(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == 'POST':
        form = SingleAccessionUploadForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    accession = accession_create(
                        creator=request.user,
                        cohort=cohort,
                        original_blob=form.cleaned_data['original_blob'],
                        original_blob_name=os.path.basename(
                            form.cleaned_data['original_blob'].name
                        ),
                        original_blob_size=form.cleaned_data['original_blob'].size,
                    )

                    metadata = {
                        key: form.cleaned_data[key]
                        for key in form.cleaned_data
                        if form.cleaned_data[key] != '' and key != 'original_blob'
                    }
                    accession.update_metadata(request.user, metadata)
            except ValidationError as e:
                messages.add_message(request, messages.ERROR, e.message)
            except MetadataValidationError as e:
                for error in e.errors():
                    messages.add_message(request, messages.ERROR, error['msg'])
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    mark_safe('Accession uploaded.'),
                )
                return HttpResponseRedirect(reverse('upload/cohort-files', args=[cohort.pk]))
    else:
        # prefill form fields with GET values, this allows links to be sent around that prefill
        # diagnosis etc.
        form = SingleAccessionUploadForm(initial=request.GET)

    return render(
        request,
        'ingest/upload_accession.html',
        {
            'form': form,
            'cohort': cohort,
        },
    )


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

    return render(request, 'ingest/upload_zip.html', {'form': form})
