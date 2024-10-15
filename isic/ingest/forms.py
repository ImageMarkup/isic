from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from isic_metadata import FIELD_REGISTRY
from isic_metadata.fields import (
    AnatomSiteGeneralEnum,
    DermoscopicTypeEnum,
    DiagnosisConfirmTypeEnum,
    DiagnosisEnum,
    ImageTypeEnum,
)
from s3_file_field.forms import S3FormFileField

from isic.core.models.collection import Collection
from isic.ingest.models import Cohort, Contributor


def choice_field_from_enum(field_name: str, enum) -> forms.ChoiceField:
    label = None

    if hasattr(FIELD_REGISTRY[field_name], "label"):
        label = FIELD_REGISTRY[field_name].label

    # sort choices by their 'label' even though we don't have labels yet
    choices = sorted(((i.value, i.value) for i in enum), key=lambda x: x[1])

    return forms.ChoiceField(choices=choices, required=False, label=label)


class CohortForm(ModelForm):
    class Meta:
        model = Cohort
        fields = ["name", "description", "default_copyright_license", "attribution"]


class ContributorForm(ModelForm):
    class Meta:
        model = Contributor
        fields = [
            "institution_name",
            "legal_contact_info",
            "default_copyright_license",
            "default_attribution",
        ]

    institution_url = forms.URLField(assume_scheme="http")


class SingleAccessionUploadForm(forms.Form):
    original_blob = S3FormFileField(model_field_id="ingest.Accession.original_blob", label="Image")

    age = forms.IntegerField(min_value=1, max_value=85, required=False)
    sex = forms.ChoiceField(choices=[("male", "male"), ("female", "female")], required=False)
    anatom_site_general = choice_field_from_enum("anatom_site_general", AnatomSiteGeneralEnum)
    diagnosis = choice_field_from_enum("diagnosis", DiagnosisEnum)
    diagnosis_confirm_type = choice_field_from_enum(
        "diagnosis_confirm_type", DiagnosisConfirmTypeEnum
    )
    image_type = choice_field_from_enum("image_type", ImageTypeEnum)
    dermoscopic_type = choice_field_from_enum("dermoscopic_type", DermoscopicTypeEnum)


class MergeCohortForm(forms.Form):
    cohort = forms.ModelChoiceField(
        widget=forms.HiddenInput(),
        queryset=Cohort.objects.all(),
        required=True,
        label="Cohort to merge into",
        help_text="The selected cohort will be the one that remains after the merge.",
    )
    cohort_to_merge = forms.ModelChoiceField(
        widget=forms.HiddenInput(),
        queryset=Cohort.objects.all(),
        required=True,
        label="Cohort to merge",
        help_text="The selected cohort will be deleted after the merge.",
    )

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = cleaned_data if cleaned_data is not None else {}
        cohort = cleaned_data.get("cohort")
        cohort_to_merge = cleaned_data.get("cohort_to_merge")

        if cohort and cohort_to_merge and cohort == cohort_to_merge:
            raise forms.ValidationError("The two cohorts must be different.")

        return cleaned_data


class PublishCohortForm(forms.Form):
    public = forms.BooleanField(
        label="Public",
        required=False,
        help_text="Make this cohort publicly accessible.",
    )

    additional_collections = forms.ModelMultipleChoiceField(
        label="Additional collections",
        queryset=Collection.objects.all(),
        required=False,
        help_text="Additional collections to add these images to.",
    )

    def clean(self):
        cleaned_data = super().clean()
        assert cleaned_data  # noqa: S101

        # note that this logic is duplicated in cohort_publish_initialize, this is just
        # added for easier form validation.
        has_public_additional_collections = Collection.objects.filter(
            pk__in=cleaned_data.get("additional_collections", []), public=True
        ).exists()

        if not cleaned_data["public"] and has_public_additional_collections:
            raise ValidationError("Can't add private images into a public collection.")

        return cleaned_data
