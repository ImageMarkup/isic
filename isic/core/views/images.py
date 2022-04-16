import json

from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404, render

from isic.core.forms.search import ImageSearchForm
from isic.core.models import Collection, Image
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.ingest.models import AccessionReview
from isic.studies.models import Study


@needs_object_permission('core.view_image', (Image, 'pk', 'pk'))
def image_detail(request, pk):
    image = get_object_or_404(
        Image.objects.select_related('accession__cohort__contributor__creator',).prefetch_related(
            Prefetch(
                'accession__checklogs', queryset=AccessionReview.objects.select_related('creator')
            )
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
        'pinned_collections': get_visible_objects(
            request.user,
            'core.view_collection',
            image.collections.filter(pinned=True).order_by('name'),
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
        ctx['metadata_versions'] = image.accession.metadata_versions.select_related(
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
