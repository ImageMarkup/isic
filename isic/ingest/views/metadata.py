import os
from typing import TypedDict

from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.query import Prefetch
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from isic_metadata.utils import get_unstructured_columns
from s3_file_field.widgets import S3FileInput

from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.models import Cohort, MetadataFile
from isic.ingest.utils.metadata import (
    ColumnRowErrors,
    Problem,
    validate_archive_consistency,
    validate_csv_format_and_filenames,
    validate_internal_consistency,
)

from . import make_breadcrumbs


class MetadataFileForm(ModelForm):
    class Meta:
        model = MetadataFile
        fields = ["blob"]
        widgets = {"blob": S3FileInput(attrs={"accept": "text/csv"})}


class ValidateMetadataForm(forms.Form):
    def __init__(self, user, cohort, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metadata_file"] = forms.ChoiceField(
            required=True,
            choices=[
                (m.id, m.id)
                for m in get_visible_objects(
                    user, "ingest.view_metadatafile", MetadataFile.objects.filter(cohort=cohort)
                )
            ],
            widget=forms.RadioSelect,
        )


@needs_object_permission("ingest.view_cohort", (Cohort, "pk", "cohort_pk"))
def metadata_file_create(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.method == "POST":
        form = MetadataFileForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.size
            form.instance.blob_name = os.path.basename(form.instance.blob.name)
            form.instance.cohort = cohort
            form.save(commit=True)

            if request.GET.get("ingest_review_redirect"):
                return HttpResponseRedirect(reverse("validate-metadata", args=[cohort.pk]))
            else:
                return HttpResponseRedirect(reverse("upload/cohort-files", args=[cohort.pk]))
    else:
        form = MetadataFileForm()

    return render(request, "ingest/metadata_file_create.html", {"form": form})


class ApplyMetadataContext(TypedDict):
    cohort: Cohort
    breadcrumbs: list[list[str]]
    metadata_file_id: int
    unstructured_columns: list[str]
    form: ValidateMetadataForm
    successful: bool

    csv_check: list[Problem] | None
    internal_check: tuple[ColumnRowErrors, list[Problem]] | None
    archive_check: tuple[ColumnRowErrors, list[Problem]] | None


@staff_member_required
def apply_metadata(request, cohort_pk):
    cohort: Cohort = get_object_or_404(
        Cohort.objects.prefetch_related(
            Prefetch("metadata_files", queryset=MetadataFile.objects.order_by("-created"))
        ),
        pk=cohort_pk,
    )

    # casting ctx to ApplyMetadataContext causes errors because all of the keys are required
    # but not provided in the initial assignment. workarounds cause more headaches than they
    # solve, so we only use the TypedDict in the tests.
    ctx = {
        "cohort": cohort,
        "breadcrumbs": make_breadcrumbs(cohort)
        + [[reverse("validate-metadata", args=[cohort.pk]), "Validate Metadata"]],
    }

    csv_check: list[Problem] | None = None
    internal_check: tuple[ColumnRowErrors, list[Problem]] | None = None
    archive_check: tuple[ColumnRowErrors, list[Problem]] | None = None

    if request.method == "POST":
        form = ValidateMetadataForm(request.user, cohort, request.POST)
        if form.is_valid():
            metadata_file = MetadataFile.objects.get(id=int(form.cleaned_data["metadata_file"]))
            ctx["metadata_file_id"] = metadata_file.pk
            df = metadata_file.to_df()
            ctx["unstructured_columns"] = get_unstructured_columns(df)

            csv_check = validate_csv_format_and_filenames(df, cohort)

            if not any(csv_check):
                internal_check = validate_internal_consistency(df)

                if not any(internal_check):
                    archive_check = validate_archive_consistency(df, cohort)

                    if not any(archive_check):
                        ctx["successful"] = True
    else:
        form = ValidateMetadataForm(request.user, cohort)

    ctx["form"] = form
    ctx["csv_check"] = csv_check
    ctx["internal_check"] = internal_check
    ctx["archive_check"] = archive_check
    return render(request, "ingest/apply_metadata.html", ctx)
