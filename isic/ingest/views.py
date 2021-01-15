from django.contrib.admin.views.decorators import staff_member_required
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls.base import reverse

from isic.ingest.models import Zip
from isic.ingest.tasks import extract_zip


class ZipForm(ModelForm):
    class Meta:
        model = Zip
        fields = ['blob']

    # def clean(self):
    #     cleaned_data = super().clean()

    def save(self, commit):
        super().save(commit)


@staff_member_required
def zip_create(request):
    if request.method == 'POST':
        form = ZipForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.blob_size = form.instance.blob.blob_size
            form.instance.blob_name = form.instance.blob.name
            form.save(commit=True)
            extract_zip.delay(form.instance.id)
            return HttpResponseRedirect(reverse('zip-detail', args=[form.instance.pk]))
    else:
        form = ZipForm()

    return render(request, 'ingest/zip_create.html', {'form': form})
