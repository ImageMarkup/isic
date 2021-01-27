from django.forms.models import ModelForm

from isic.ingest.models import Cohort


class CohortForm(ModelForm):
    class Meta:
        model = Cohort
        fields = ['name', 'description']
