from django import forms
from django.forms.forms import Form
from django.forms.models import ModelForm
from s3_file_field.widgets import S3FileInput

from isic.ingest.models import Cohort, Contributor
from isic.ingest.models.accession import Accession


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


class SingleAccessionUploadForm(Form):
    fields = forms.fields_for_model(
        Accession,
        ['original_blob'],
        widgets={'original_blob': S3FileInput(attrs={'accept': 'image/*;capture=camera'})},
    )

    original_blob = fields['original_blob']
