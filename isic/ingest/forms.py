from django import forms
from django.forms.models import ModelForm
from s3_file_field.forms import S3FormFileField

from isic.ingest.models import Cohort, Contributor


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

    age = forms.CharField(required=False)
    sex = forms.CharField(required=False)
    anatom_site_general = forms.CharField(required=False)
    diagnosis = forms.CharField(required=False)
    diagnosis_confirm_type = forms.CharField(required=False)
