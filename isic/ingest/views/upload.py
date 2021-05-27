from django.contrib.auth.decorators import login_required
from django.db.models.query import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.ingest.forms import CohortForm, ContributorForm
from isic.ingest.models import Cohort, Contributor, MetadataFile


@login_required
def select_or_create_contributor(request):
    if request.user.is_staff:
        contributors = Contributor.objects.all()
    else:
        contributors = Contributor.objects.filter(creator=request.user)

    ctx = {'contributors': contributors}
    if ctx['contributors'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-contributor'))

    return render(request, 'ingest/contributor_select_or_create.html', ctx)


@login_required
def select_or_create_cohort(request, contributor_pk):
    filters = {'contributor__pk': contributor_pk}

    if not request.user.is_staff:
        filters['contributor__creator'] = request.user

    ctx = {
        'cohorts': Cohort.objects.filter(**filters).order_by('-created'),
        'contributor_pk': contributor_pk,
    }
    if ctx['cohorts'].count() == 0:
        return HttpResponseRedirect(reverse('upload/create-cohort', args=[contributor_pk]))

    return render(request, 'ingest/cohort_select_or_create.html', ctx)


@login_required
def upload_contributor_create(request):
    if request.method == 'POST':
        form = ContributorForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.instance.owners.add(request.user)
            form.save(commit=True)
            return HttpResponseRedirect(reverse('upload/create-cohort', args=[form.instance.pk]))
    else:
        form = ContributorForm()

    return render(request, 'ingest/contributor_create.html', {'form': form})


@login_required
def upload_cohort_create(request, contributor_pk):
    filters = {}
    if not request.user.is_staff:
        filters['creator'] = request.user

    contributor: Contributor = get_object_or_404(
        Contributor.objects.filter(**filters), pk=contributor_pk
    )

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
def cohort_files(request, pk):
    filters = {}
    if not request.user.is_staff:
        filters['contributor__creator'] = request.user

    cohort = get_object_or_404(
        Cohort.objects.filter(**filters)
        .prefetch_related(
            Prefetch('metadata_files', queryset=MetadataFile.objects.order_by('-created'))
        )
        .prefetch_related('zips'),
        pk=pk,
    )
    return render(
        request,
        'ingest/cohort_files.html',
        {
            'cohort': cohort,
        },
    )
