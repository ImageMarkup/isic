from django import forms
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

from isic.ingest.models import Cohort, Contributor


def choice_field_from_enum(field_name: str, enum) -> forms.ChoiceField:
    label = None

    if 'label' in FIELD_REGISTRY[field_name]:
        label = FIELD_REGISTRY[field_name]['label']

    # sort choices by their 'label' even though we don't have labels yet
    choices = sorted(((i.value, i.value) for i in enum), key=lambda x: x[1])

    return forms.ChoiceField(choices=choices, required=False, label=label)


class CohortForm(ModelForm):
    class Meta:
        model = Cohort
        fields = ['name', 'description', 'copyright_license', 'attribution']


class ContributorForm(ModelForm):
    class Meta:
        model = Contributor
        fields = [
            'institution_name',
            'institution_url',
            'legal_contact_info',
            'default_copyright_license',
            'default_attribution',
        ]


class SingleAccessionUploadForm(forms.Form):
    original_blob = S3FormFileField(model_field_id='ingest.Accession.original_blob', label='Image')

    age = forms.IntegerField(min_value=1, max_value=85, required=False)
    sex = forms.ChoiceField(choices=[('male', 'male'), ('female', 'female')], required=False)
    anatom_site_general = choice_field_from_enum('anatom_site_general', AnatomSiteGeneralEnum)
    diagnosis = choice_field_from_enum('diagnosis', DiagnosisEnum)
    diagnosis_confirm_type = choice_field_from_enum(
        'diagnosis_confirm_type', DiagnosisConfirmTypeEnum
    )
    image_type = choice_field_from_enum('image_type', ImageTypeEnum)
    dermoscopic_type = choice_field_from_enum('dermoscopic_type', DermoscopicTypeEnum)
