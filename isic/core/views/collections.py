from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query_utils import Q
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.filters import CollectionFilter
from isic.core.forms.collection import CollectionForm
from isic.core.forms.doi import CreateDoiForm
from isic.core.models import Collection
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.models import Contributor


def collection_list(request):
    # TODO: should the image count be access controlled too?
    collections = get_visible_objects(
        request.user,
        'core.view_collection',
        Collection.objects.annotate(num_images=Count('images', distinct=True)).order_by(
            '-pinned', 'name'
        ),
    )
    if request.user.is_authenticated:
        counts = collections.aggregate(
            pinned=Count('pk', filter=Q(pinned=True)),
            shared_with_me=Count('pk', filter=Q(shares=request.user)),
            mine=Count('pk', filter=Q(creator=request.user)),
            all_=Count('pk'),
        )
    else:
        counts = collections.aggregate(
            pinned=Count('pk', filter=Q(pinned=True)),
            all_=Count('pk'),
        )

    filter = CollectionFilter(request.GET, queryset=collections, user=request.user)
    paginator = Paginator(filter.qs, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'core/collection_list.html',
        {'collections': page, 'filter': filter, 'counts': counts},
    )


@login_required
def collection_create(request):
    context = {}

    if request.method == 'POST':
        context['form'] = CollectionForm(request.POST)
        if context['form'].is_valid():
            collection = context['form'].save(commit=False)
            collection.creator = request.user
            collection.save()
            return HttpResponseRedirect(reverse('core/collection-detail', args=[collection.pk]))
    else:
        context['form'] = CollectionForm()

    return render(
        request,
        'core/collection_create_or_edit.html',
        context,
    )


@needs_object_permission('core.edit_collection', (Collection, 'pk', 'pk'))
def collection_edit(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    form = CollectionForm(request.POST or None, instance=collection)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return HttpResponseRedirect(reverse('core/collection-detail', args=[collection.pk]))

    return render(
        request, 'core/collection_create_or_edit.html', {'form': form, 'collection': collection}
    )


@needs_object_permission('core.view_collection', (Collection, 'pk', 'pk'))
@needs_object_permission('core.create_doi', (Collection, 'pk', 'pk'))
def collection_create_doi(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    context = {'collection': collection}

    if not collection.images.exists():
        context['warnings'] = ['An empty collection cannot be published.']
    else:
        if request.method == 'POST':
            context['form'] = CreateDoiForm(request.POST, collection=collection, request=request)
            if context['form'].is_valid():
                context['form'].save()
                # TODO flash message
                return HttpResponseRedirect(reverse('core/collection-detail', args=[collection.pk]))
        else:
            context['form'] = CreateDoiForm(
                collection=collection,
                request=request,
            )

        preview = collection.as_datacite_doi(
            request.user, f'{settings.ISIC_DATACITE_DOI_PREFIX}/123456'
        )['data']['attributes']
        preview['creators'] = ', '.join([c['name'] for c in preview['creators']])
        context['preview'] = preview

        if not collection.public or collection.images.filter(public=False).exists():
            context['warnings'] = ['The collection or some of the images in it are private.']

    return render(
        request,
        'core/collection_create_doi.html',
        context,
    )


@needs_object_permission('core.view_collection', (Collection, 'pk', 'pk'))
def collection_detail(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    # TODO; if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        'core.view_image',
        collection.images.select_related('accession').order_by('created').distinct(),
    )
    paginator = Paginator(images, 30)
    page = paginator.get_page(request.GET.get('page'))
    contributors = get_visible_objects(
        request.user,
        'ingest.view_contributor',
        Contributor.objects.filter(
            pk__in=collection.images.values('accession__cohort__contributor__pk').distinct()
        ).order_by('institution_name'),
    )

    image_removal_mode = (
        request.GET.get('image_removal_mode')
        and not collection.locked
        and request.user.has_perm('core.edit_collection', collection)
    )

    return render(
        request,
        'core/collection_detail.html',
        {
            'collection': collection,
            'contributors': contributors,
            'images': page,
            'num_images': paginator.count,
            'image_removal_mode': image_removal_mode,
        },
    )
