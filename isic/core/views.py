from collections import defaultdict
import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.filters import CollectionFilter
from isic.core.forms.collection import CollectionForm
from isic.core.forms.doi import CreateDoiForm
from isic.core.forms.search import ImageSearchForm
from isic.core.models import Collection, Image
from isic.core.models.segmentation import Segmentation, SegmentationReview
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.models import CheckLog, Contributor
from isic.ingest.models.accession import Accession
from isic.ingest.models.metadata_file import MetadataFile
from isic.ingest.models.zip_upload import ZipUpload
from isic.studies.models import Annotation, Study, StudyTask


def key_by(sequence, f):
    r = defaultdict(list)
    for item in sequence:
        r[f(item)].append(item)
    return dict(r)


@needs_object_permission('auth.view_staff')
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
    if request.user.is_authenticated:
        counts = collections.aggregate(
            official=Count('pk', filter=Q(official=True)),
            shared_with_me=Count('pk', filter=Q(shares=request.user)),
            mine=Count('pk', filter=Q(creator=request.user)),
            all_=Count('pk'),
        )
    else:
        counts = collections.aggregate(
            official=Count('pk', filter=Q(official=True)),
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


@staff_member_required
def user_detail(request, pk):
    user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    ctx = {
        'user': user,
        'email_addresses': user.emailaddress_set.order_by('-primary', '-verified', 'email'),
    }

    ctx['sections'] = {
        'collections': Collection.objects.filter(creator=user).order_by('-created'),
        'contributors': Contributor.objects.select_related('creator')
        .prefetch_related('owners')
        .filter(owners=user)
        .order_by('-created'),
        'zip_uploads': ZipUpload.objects.select_related('cohort', 'creator')
        .filter(creator=user)
        .order_by('-created'),
        'single_shot_accessions': Accession.objects.select_related('cohort', 'creator')
        .filter(zip_upload=None, creator=user)
        .order_by('-created'),
        'accession_reviews': CheckLog.objects.select_related('creator')
        .filter(creator=user)
        .order_by('-created'),
        'metadata_files': MetadataFile.objects.select_related('cohort', 'creator')
        .filter(creator=user)
        .order_by('-created'),
        'studies': Study.objects.select_related('creator', 'collection')
        .filter(creator=user)
        .order_by('-created'),
        'study_tasks': StudyTask.objects.select_related('annotator', 'image')
        .filter(annotator=user)
        .order_by('-created'),
        'annotations': Annotation.objects.select_related('study', 'annotator', 'image')
        .filter(annotator=user)
        .order_by('-created'),
        'segmentations': Segmentation.objects.select_related('creator', 'image')
        .filter(creator=user)
        .order_by('-created'),
        'segmentation_reviews': SegmentationReview.objects.select_related('creator', 'segmentation')
        .filter(creator=user)
        .order_by('-created'),
    }

    return render(request, 'core/user_detail.html', ctx)


@needs_object_permission('core.view_image', (Image, 'pk', 'pk'))
def image_detail(request, pk):
    image = get_object_or_404(
        Image.objects.select_related('accession__cohort__contributor__creator',).prefetch_related(
            Prefetch('accession__checklogs', queryset=CheckLog.objects.select_related('creator'))
        ),
        pk=pk,
    )

    studies = get_visible_objects(
        request.user,
        'studies.view_study',
        Study.objects.select_related('creator'),
    )
    studies = (
        studies.filter(tasks__image=image)
        .annotate(
            num_responses=Count(
                'tasks__annotation__responses', filter=Q(tasks__image=image), distinct=True
            )
        )
        .annotate(
            num_markups=Count(
                'tasks__annotation__markups', filter=Q(tasks__image=image), distinct=True
            )
        )
        .distinct()
    )

    ctx = {
        'image': image,
        'official_collections': get_visible_objects(
            request.user,
            'core.view_collection',
            image.collections.filter(official=True).order_by('name'),
        ),
        'other_patient_images': get_visible_objects(
            request.user, 'core.view_image', image.same_patient_images().select_related('accession')
        ),
        'other_lesion_images': get_visible_objects(
            request.user, 'core.view_image', image.same_lesion_images().select_related('accession')
        ),
        'studies': studies,
    }

    if request.user.has_perm('core.view_full_metadata', image):
        ctx['metadata'] = dict(sorted(image.accession.metadata.items()))
        ctx['unstructured_metadata'] = dict(sorted(image.accession.unstructured_metadata.items()))
        ctx['metadata_revisions'] = image.accession.metadata_revisions.select_related(
            'creator'
        ).differences()
    else:
        ctx['metadata'] = dict(sorted(image.accession.redacted_metadata.items()))

    ctx['sections'] = {
        'metadata': 'Metadata',
        'studies': f'Studies ({studies.count()})',
    }

    if request.user.is_staff:
        ctx['sections'][
            'patient_images'
        ] = f'Other Patient Images ({ctx["other_patient_images"].count()})'
        ctx['sections'][
            'lesion_images'
        ] = f'Other Lesion Images ({ctx["other_lesion_images"].count()})'
        ctx['sections']['ingestion_details'] = 'Ingestion Details'

    return render(request, 'core/image_detail/base.html', ctx)


def image_browser(request):
    collections = get_visible_objects(
        request.user, 'core.view_collection', Collection.objects.order_by('name')
    )
    search_form = ImageSearchForm(
        request.GET,
        user=request.user,
        collections=collections,
    )
    qs: QuerySet[Image] = Image.objects.none()
    if search_form.is_valid():
        qs = search_form.results

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    if request.user.is_authenticated:
        addable_collections = collections.filter(locked=False)

        if not request.user.is_staff:
            addable_collections = addable_collections.filter(creator=request.user)
    else:
        addable_collections = []

    return render(
        request,
        'core/image_browser.html',
        {
            'total_images': qs.count(),
            'images': page,
            # The user can only add images to collections that are theirs and unlocked.
            'collections': addable_collections,
            # This gets POSTed to the populate endpoint if called
            'search_body': json.dumps(request.GET),
            'form': search_form,
        },
    )
