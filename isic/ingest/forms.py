import os

from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from s3_file_field.widgets import S3FileInput, S3PlaceholderFile

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


class SingleAccessionUploadForm(ModelForm):
    class Meta:
        model = Accession
        fields = [
            'original_blob',
        ]
        widgets = {'original_blob': S3FileInput(attrs={'accept': 'image/*;capture=camera'})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.cohort = kwargs.pop('cohort')
        super().__init__(*args, **kwargs)

    def clean_original_blob(self) -> S3PlaceholderFile:
        value: S3PlaceholderFile = self.cleaned_data['original_blob']
        blob_name = os.path.basename(value.name)

        if self.cohort.accessions.filter(blob_name=blob_name).exists():
            raise ValidationError('An accession with the same name already exists.')

        return value

    def clean(self):
        cleaned_data = super().clean()

        if not self.user.has_perm('ingest.add_accession', self.cohort):
            raise ValidationError(
                f'You do not have permission to add an image to {self.cohort.name}'
            )

        return cleaned_data
