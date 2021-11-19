from collections import defaultdict
import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.forms.doi import CreateDoiForm
from isic.core.forms.search import ImageSearchForm
from isic.core.models import Collection, Image
from isic.core.permissions import get_visible_objects, permission_or_404
from isic.core.stats import get_archive_stats
from isic.ingest.models import CheckLog, Contributor
from isic.studies.models import Markup, Response, Study


def key_by(sequence, f):
    r = defaultdict(list)
    for item in sequence:
        r[f(item)].append(item)
    return dict(r)


def stats(request):
    ctx = {}
    archive_stats = get_archive_stats()

    ctx['stats'] = [
        [
            ('Users', archive_stats['total_users_count']),
            ('Uploading Users', archive_stats['uploaders_count']),
            ('Annotating Users', archive_stats['annotating_users_count']),
        ],
        [
            ('Contributors', archive_stats['contributors_count']),
            ('', ''),
            ('Collections', archive_stats['collections_count']),
        ],
        [
            ('Images', archive_stats['images_count']),
            ('Public Images', archive_stats['public_images_count']),
            ('Annotated Images', archive_stats['annotated_images_count']),
        ],
        [
            ('Studies', archive_stats['studies_count']),
            ('Public Studies', archive_stats['public_studies_count']),
            ('', ''),
        ],
        [
            ('Annotations', archive_stats['annotations_count']),
            ('Markups', archive_stats['markups_count']),
            ('Responses', archive_stats['responses_count']),
        ],
    ]
    return render(request, 'core/stats.html', ctx)


@permission_or_404('auth.view_staff')
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by('email')
    return render(request, 'core/staff_list.html', {'users': users, 'total_users': User.objects})


def collection_list(request):
    # TODO: should the image count be access controlled too?
    collections = get_visible_objects(
        request.user,
        'core.view_collection',
        Collection.objects.annotate(num_images=Count('images', distinct=True)).order_by(
            '-official', 'name'
        ),
    )
    paginator = Paginator(collections, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'core/collection_list.html',
        {'collections': page},
    )


@permission_or_404('core.view_collection', (Collection, 'pk', 'pk'))
@permission_or_404('core.create_doi', (Collection, 'pk', 'pk'))
def collection_create_doi(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    context = {'collection': collection}

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


@permission_or_404('core.view_collection', (Collection, 'pk', 'pk'))
def collection_detail(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    # TODO; if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        'core.view_image',
        collection.images.select_related('accession').order_by('created'),
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

    return render(
        request,
        'core/collection_detail.html',
        {
            'collection': collection,
            'contributors': contributors,
            'images': page,
            'num_images': paginator.count,
        },
    )


# TODO: refactor permissions in the future to use permission_or_404 and filtering
# only visible studies/responses
# TODO: never show unstructured metadata to non-staff users (maybe also in cohort review pages)
@staff_member_required
def image_detail(request, pk):
    image = get_object_or_404(
        Image.objects.select_related(
            'accession__cohort__contributor__creator',
        )
        .prefetch_related(
            Prefetch('accession__checklogs', queryset=CheckLog.objects.select_related('creator'))
        )
        .prefetch_related(Prefetch('collections', queryset=Collection.objects.order_by('name'))),
        pk=pk,
    )

    studies = Study.objects.filter(tasks__image=image).distinct()

    responses = (
        Response.objects.filter(annotation__task__study__in=studies, annotation__image=image)
        .select_related('annotation__annotator', 'choice', 'question', 'annotation__task__study')
        .order_by('question__prompt', 'annotation__annotator')
    )
    markups = (
        Markup.objects.filter(annotation__task__study__in=studies, annotation__image=image)
        .select_related('annotation__annotator', 'annotation__task__study', 'feature')
        .order_by('feature__name', 'annotation__annotator')
    )

    return render(
        request,
        'core/image_detail.html',
        {
            'image': image,
            'studies': studies,
            'responses': key_by(responses, lambda r: r.annotation.task.study.pk),
            'markups': key_by(markups, lambda r: r.annotation.task.study.pk),
            'meta': json.dumps(image.accession.metadata, indent=2),
            'unstructured': json.dumps(image.accession.unstructured_metadata, indent=2),
            'sections': {
                'metadata': 'Metadata',
                'studies': f'Studies ({studies.count()})',
                'ingest-review': 'Ingest Review',
            },
        },
    )


def image_browser(request):
    search_form = ImageSearchForm(
        request.GET,
        user=request.user,
        collections=get_visible_objects(
            request.user, 'core.view_collection', Collection.objects.order_by('name')
        ),
    )
    search_form.is_valid()

    paginator = Paginator(search_form.results, 30)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'core/image_browser.html',
        {
            'images': page,
            'form': search_form,
        },
    )
