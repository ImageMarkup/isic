import os

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.query import Prefetch
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from isic_metadata.utils import get_unstructured_columns
from s3_file_field.widgets import S3FileInput

from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.models import Accession, Cohort, MetadataFile
from isic.ingest.utils.metadata import (
    validate_archive_consistency,
    validate_csv_format_and_filenames,
    validate_internal_consistency,
)

from . import make_breadcrumbs


class MetadataFileForm(ModelForm):
    class Meta:
        model = MetadataFile
        fields = ['blob']
        widgets = {'blob': S3FileInput(attrs={'accept': 'text/csv'})}


class ValidateMetadataForm(forms.Form):
    def __init__(self, user, cohort, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['metadata_file'] = forms.ChoiceField(
            required=True,
            choices=[
                (m.id, m.id)
                for m in get_visible_objects(
                    user, 'ingest.view_metadatafile', MetadataFile.objects.filter(cohort=cohort)
                )
            ],
            widget=forms.RadioSelect,
        )


@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def metadata_file_create(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == 'POST':
        form = MetadataFileForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = os.path.basename(form.instance.blob.name)
            form.instance.cohort = cohort
            form.save(commit=True)

            if request.GET.get('ingest_review_redirect'):
                return HttpResponseRedirect(reverse('validate-metadata', args=[cohort.pk]))
            else:
                return HttpResponseRedirect(reverse('upload/cohort-files', args=[cohort.pk]))
    else:
        form = MetadataFileForm()

    return render(request, 'ingest/metadata_file_create.html', {'form': form})


@staff_member_required
def reset_metadata(request, cohort_pk):
    # TODO: GET request to mutate?
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    Accession.objects.filter(cohort=cohort).update(metadata={})
    messages.info(request, 'Metadata has been reset.')
    return HttpResponseRedirect(reverse('cohort-detail', args=[cohort_pk]))


@staff_member_required
def apply_metadata(request, cohort_pk):
    cohort = get_object_or_404(
        Cohort.objects.prefetch_related(
            Prefetch('metadata_files', queryset=MetadataFile.objects.order_by('-created'))
        ),
        pk=cohort_pk,
    )

    ctx = {
        'cohort': cohort,
        'breadcrumbs': make_breadcrumbs(cohort)
        + [[reverse('validate-metadata', args=[cohort.id]), 'Validate Metadata']],
    }
    # TODO: Find a cleaner way to implement this system altogether.
    checkpoints = {
        1: {
            'title': 'Filename checks',
            'run': False,
            'problems': {},
        },
        2: {
            'title': 'Internal consistency',
            'run': False,
            'problems': {},
        },
        3: {
            'title': 'Archive consistency',
            'run': False,
            'problems': {},
        },
    }

    if request.method == 'POST':
        form = ValidateMetadataForm(request.user, cohort, request.POST)
        if form.is_valid():
            metadata_file = MetadataFile.objects.get(id=int(form.cleaned_data['metadata_file']))
            ctx['metadata_file_id'] = metadata_file.id
            df = metadata_file.to_df()
            ctx['unstructured_columns'] = get_unstructured_columns(df)

            checkpoints[1]['problems'] = validate_csv_format_and_filenames(df, cohort)
            checkpoints[1]['run'] = True

            if not checkpoints[1]['problems']:
                checkpoints[2]['problems'] = validate_internal_consistency(df)
                checkpoints[2]['run'] = True

                if not checkpoints[2]['problems']:
                    checkpoints[3]['problems'] = validate_archive_consistency(df, cohort)
                    checkpoints[3]['run'] = True

                    if not checkpoints[3]['problems']:
                        ctx['successful'] = True

    else:
        form = ValidateMetadataForm(request.user, cohort)

    ctx['checkpoint'] = checkpoints
    ctx['form'] = form
    return render(request, 'ingest/apply_metadata.html', ctx)
