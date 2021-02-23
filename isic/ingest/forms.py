from django.forms.models import ModelForm

from isic.ingest.models import Cohort, Contributor


class CohortForm(ModelForm):
    class Meta:
        model = Cohort
        fields = ['contributor', 'name', 'description', 'copyright_license', 'attribution']


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
