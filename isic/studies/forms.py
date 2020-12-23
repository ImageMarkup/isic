from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from django.forms.widgets import SelectMultiple

from isic.studies.models import Image, Study
from isic.studies.tasks import create_study_task


class Select2SelectMultiple(SelectMultiple):
    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/select2@4.1.0-beta.1/dist/css/select2.min.css',)
        }
        js = ('https://cdn.jsdelivr.net/npm/select2@4.1.0-beta.1/dist/js/select2.min.js',)


class StudyForm(ModelForm):
    class Meta:
        model = Study
        fields = ['name', 'description', 'features', 'questions']

    images = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Image IDs, one per line'})
    )
    # use browser-default to disable materialize styling of this select
    annotators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=Select2SelectMultiple(attrs={'class': 'browser-default'}),
    )

    def clean(self):
        cleaned_data = super().clean()

        image_ids = cleaned_data.get('images').split()
        self.images = Image.objects.filter(object_id__in=image_ids)

        if self.images.count() != len(image_ids):
            raise ValidationError('Some of the image ids do not exist.')

    def save(self, commit):
        super().save(commit)

        for annotator in self.cleaned_data['annotators']:
            for image in self.images:
                create_study_task.delay(self.instance.id, annotator.id, image.id)
