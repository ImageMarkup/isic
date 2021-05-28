from collections import defaultdict
import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render

from isic.core.models import Collection, Image
from isic.ingest.models import CheckLog, Contributor, Zip
from isic.login.girder import get_girder_db
from isic.studies.models import Annotation, Markup, Response, Study


def key_by(sequence, f):
    r = defaultdict(list)
    for item in sequence:
        r[f(item)].append(item)
    return dict(r)


def stats(request):
    ctx = {
        'num_annotations': Annotation.objects.count(),
        'num_collections': Collection.objects.count(),
        'num_contributors': Contributor.objects.count(),
        'num_images': Image.objects.count(),
        'num_markups': Markup.objects.count(),
        'num_public_images': Image.objects.filter(public=True).count(),
        'num_public_studies': Study.objects.filter(public=True).count(),
        'num_responses': Response.objects.count(),
        'num_studies': Study.objects.count(),
        'num_annotated_images': Annotation.objects.values('image').distinct().count(),
        'num_uploaders': Zip.objects.values('creator').distinct().count(),
        'num_annotating_users': Annotation.objects.values('annotator').distinct().count(),
    }

    if settings.ISIC_MONGO_URI:
        ctx['num_total_users'] = get_girder_db()['user'].count()
    else:
        ctx['num_total_users'] = 0

    ctx['stats'] = [
        [
            ('Users', ctx['num_total_users']),
            ('Uploading Users', ctx['num_uploaders']),
            ('Annotating Users', ctx['num_annotating_users']),
        ],
        [
            ('Contributors', ctx['num_contributors']),
            ('', ''),
            ('Collections', ctx['num_collections']),
        ],
        [
            ('Images', ctx['num_images']),
            ('Public Images', ctx['num_public_images']),
            ('Annotated Images', ctx['num_annotated_images']),
        ],
        [('Studies', ctx['num_studies']), ('Public Studies', ctx['num_public_studies']), ('', '')],
        [
            ('Annotations', ctx['num_annotations']),
            ('Markups', ctx['num_markups']),
            ('Responses', ctx['num_responses']),
        ],
    ]

    return render(request, 'core/stats.html', ctx)


@staff_member_required
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by('email')
    return render(request, 'core/staff_list.html', {'users': users, 'total_users': User.objects})


@staff_member_required
def collection_list(request):
    collections = Collection.objects.annotate(num_images=Count('images', distinct=True)).order_by(
        '-name'
    )
    paginator = Paginator(collections, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'core/collection_list.html',
        {'collections': page},
    )


@staff_member_required
def collection_detail(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    images = collection.images.order_by('created')
    paginator = Paginator(images, 30)
    page = paginator.get_page(request.GET.get('page'))
    contributors = Contributor.objects.filter(
        pk__in=collection.images.values('accession__upload__cohort__contributor__pk').distinct()
    ).order_by('institution_name')

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
def image_detail(request, id_or_gid_or_isicid):
    filters = Q(isic_id=id_or_gid_or_isicid) | Q(accession__girder_id=id_or_gid_or_isicid)
    if id_or_gid_or_isicid.isnumeric():
        filters |= Q(pk=id_or_gid_or_isicid)

    image = get_object_or_404(
        Image.objects.select_related(
            'accession__upload__cohort__contributor__creator',
        )
        .prefetch_related(
            Prefetch('accession__checklogs', queryset=CheckLog.objects.select_related('creator'))
        )
        .prefetch_related(Prefetch('collections', queryset=Collection.objects.order_by('name'))),
        filters,
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
