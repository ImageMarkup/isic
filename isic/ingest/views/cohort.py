from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import needs_object_permission
from isic.ingest.models import Cohort
from isic.ingest.services.cohort import cohort_publish_initialize
from isic.ingest.views import make_breadcrumbs


@staff_member_required
def cohort_detail(request, pk):
    cohort = get_object_or_404(Cohort.objects.select_related('creator'), pk=pk)
    paginator = Paginator(cohort.accessions.ingested(), 50)
    accessions = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/cohort_detail.html',
        {
            'cohort': cohort,
            'accessions': accessions,
            'breadcrumbs': make_breadcrumbs(cohort),
        },
    )


@staff_member_required  # TODO: who gets to publish a cohort? anyone who can view it?
@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'pk'))
def publish_cohort(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)

    if request.method == 'POST':
        public = True if 'public' in request.POST else False
        cohort_publish_initialize(cohort=cohort, publisher=request.user, public=public)

        messages.add_message(
            request,
            messages.SUCCESS,
            f'Publishing {intcomma(cohort.accessions.publishable().count())} images. This may take several minutes.',  # noqa: E501
        )
        return HttpResponseRedirect(reverse('cohort-detail', args=[cohort.pk]))
    else:
        ctx = {
            'cohort': cohort,
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Publish Cohort']],
            'num_accessions': cohort.accessions.count(),
            'num_published': cohort.accessions.published().count(),
            'num_publishable': cohort.accessions.publishable().count(),
            'num_rejected': cohort.accessions.rejected().count(),
            'num_pending': cohort.accessions.ingesting().count(),
            'num_uningested': cohort.accessions.uningested().count(),
        }

    ctx['num_unpublishable'] = ctx['num_accessions'] - ctx['num_publishable']

    return render(request, 'ingest/cohort_publish.html', ctx)
