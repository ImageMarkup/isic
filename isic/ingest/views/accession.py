from collections import defaultdict
import itertools

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import needs_object_permission
from isic.ingest.forms import MergeCohortForm
from isic.ingest.models import Cohort
from isic.ingest.models.accession import Accession, AccessionStatus
from isic.ingest.models.contributor import Contributor
from isic.ingest.services.cohort import cohort_merge, cohort_publish_initialize
from isic.ingest.views import make_breadcrumbs


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
