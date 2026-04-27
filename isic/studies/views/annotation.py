from django.contrib.admin.views.decorators import staff_member_required
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from isic.studies.models import Annotation, Markup


@staff_member_required
def view_mask(request, markup_id):
    markup = get_object_or_404(Markup.objects.values("mask"), pk=markup_id)
    return HttpResponseRedirect(markup["mask"].url)


@staff_member_required
def annotation_detail(request, pk):
    annotation = get_object_or_404(
        Annotation.objects.select_related("image", "study", "annotator")
        .prefetch_related("markups__feature")
        .prefetch_related("responses__choice")
        .prefetch_related("responses__question"),
        pk=pk,
    )
    return render(
        request,
        "studies/annotation_detail.html",
        {"annotation": annotation},
    )
