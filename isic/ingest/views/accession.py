from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from isic.ingest.models.accession import Accession


@staff_member_required
def accession_cog_viewer(request, pk):
    accession = get_object_or_404(Accession, pk=pk)

    return render(
        request,
        "ingest/accession_cog_viewer.html",
        {
            "accession": accession,
        },
    )
