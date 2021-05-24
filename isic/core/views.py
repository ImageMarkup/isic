from collections import defaultdict
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from isic.core.models import Image
from isic.ingest.models import CheckLog
from isic.studies.models import Markup, Response, Study


def key_by(sequence, f):
    r = defaultdict(list)
    for item in sequence:
        r[f(item)].append(item)
    return dict(r)


@staff_member_required
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by('email')
    return render(request, 'core/staff_list.html', {'users': users, 'total_users': User.objects})


@staff_member_required
def image_detail(request, id_or_gid_or_isicid):
    filters = Q(isic_id=id_or_gid_or_isicid) | Q(accession__girder_id=id_or_gid_or_isicid)
    if id_or_gid_or_isicid.isnumeric():
        filters |= Q(pk=id_or_gid_or_isicid)

    image = get_object_or_404(
        Image.objects.select_related(
            'accession__upload__cohort__contributor__creator',
        ).prefetch_related(
            Prefetch('accession__checklogs', queryset=CheckLog.objects.select_related('creator'))
        ),
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
            'tags': sorted(image.accession.tags),
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
