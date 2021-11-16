from django.contrib.auth.decorators import login_required
from django.db.models.query import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import get_visible_objects, permission_or_404
from isic.ingest.forms import CohortForm, ContributorForm
from isic.ingest.models import Cohort, Contributor, MetadataFile


@login_required
def select_or_create_contributor(request):
    ctx = {'contributors': get_visible_objects(request.user, 'ingest.view_contributor')}
    if ctx['contributors'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-contributor'))

    return render(request, 'ingest/contributor_select_or_create.html', ctx)


@permission_or_404('ingest.view_contributor', (Contributor, 'pk', 'contributor_pk'))
def select_or_create_cohort(request, contributor_pk):
    contributor = Contributor.objects.get(pk=contributor_pk)
    ctx = {
        'cohorts': contributor.cohorts.order_by('-created'),
        'contributor_pk': contributor_pk,
    }
    if ctx['cohorts'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-cohort', args=[contributor_pk]))

    return render(request, 'ingest/cohort_select_or_create.html', ctx)


@login_required
@permission_or_404('ingest.create_contributor')
def upload_contributor_create(request):
    if request.method == 'POST':
        form = ContributorForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.save(commit=True)
            # The instance must be saved before ManyToMany relationships can be added
            form.instance.owners.add(request.user)
            return HttpResponseRedirect(reverse('upload/create-cohort', args=[form.instance.pk]))
    else:
        form = ContributorForm()

    return render(request, 'ingest/contributor_create.html', {'form': form})


@login_required
@permission_or_404('ingest.create_cohort', (Contributor, 'pk', 'contributor_pk'))
def upload_cohort_create(request, contributor_pk):
    contributor: Contributor = get_object_or_404(Contributor, pk=contributor_pk)

    if request.method == 'POST':
        form = CohortForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.contributor = contributor
            form.save(commit=True)
            return HttpResponseRedirect(reverse('upload/cohort-files', args=[form.instance.pk]))
    else:
        form = CohortForm(
            initial={
                'contributor': contributor.pk,
                'copyright_license': contributor.default_copyright_license,
                'attribution': contributor.default_attribution,
            }
        )

    return render(request, 'ingest/cohort_create.html', {'form': form})


@login_required
@permission_or_404('ingest.view_cohort', (Cohort, 'pk', 'pk'))
def cohort_files(request, pk):
    cohort = get_object_or_404(
        Cohort.objects.prefetch_related(
            Prefetch('metadata_files', queryset=MetadataFile.objects.order_by('-created'))
        ).prefetch_related('zip_uploads'),
        pk=pk,
    )
    return render(
        request,
        'ingest/cohort_files.html',
        {
            'cohort': cohort,
        },
    )
