from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls.base import reverse

from isic.ingest.forms import MergeContributorForm
from isic.ingest.services.contributor import merge_contributors


@staff_member_required
def contributor_merge(request):
    form = MergeContributorForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        contributor = form.cleaned_data["contributor"]
        contributor_to_merge = form.cleaned_data["contributor_to_merge"]
        try:
            merge_contributors(dest_contributor=contributor, src_contributor=contributor_to_merge)
        except ValidationError as e:
            form.add_error(None, e)
        else:
            messages.success(request, "Contributor merged successfully.")
            return HttpResponseRedirect(reverse("ingest/cohort-list"))

    return render(
        request,
        "ingest/contributor_merge.html",
        {"form": form},
    )
