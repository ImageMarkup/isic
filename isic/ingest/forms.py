from django import forms
from django.forms.models import ModelForm
from isic_metadata.fields import AnatomSiteGeneralEnum, DiagnosisConfirmTypeEnum, DiagnosisEnum
from s3_file_field.forms import S3FormFileField

from isic.ingest.models import Cohort, Contributor

BLANK_CHOICE = ('', '')


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

    age = forms.ChoiceField(choices=[BLANK_CHOICE] + [(x, x) for x in range(1, 86)], required=False)
    sex = forms.ChoiceField(
        choices=[BLANK_CHOICE, ('male', 'male'), ('female', 'female')], required=False
    )
    anatom_site_general = forms.ChoiceField(
        choices=[BLANK_CHOICE] + [(i.value, i.value) for i in AnatomSiteGeneralEnum], required=False
    )
    diagnosis = forms.ChoiceField(
        choices=[BLANK_CHOICE] + [(i.value, i.value) for i in DiagnosisEnum], required=False
    )
    diagnosis_confirm_type = forms.ChoiceField(
        choices=[BLANK_CHOICE] + [(i.value, i.value) for i in DiagnosisConfirmTypeEnum],
        required=False,
    )
