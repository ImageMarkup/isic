from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from isic.core.permissions import get_visible_objects, permission_or_404
from isic.studies.models import Annotation, Markup, Study, StudyTask


def study_list(request):
    studies = get_visible_objects(
        request.user,
        'studies.view_study',
        Study.objects.select_related('creator').distinct().order_by('-created'),
    )
    paginator = Paginator(studies, 10)
    studies_page = paginator.get_page(request.GET.get('page'))

    num_participants = dict(
        StudyTask.objects.values('study')
        .filter(study__in=studies_page)
        .annotate(count=Count('annotator', distinct=True))
        .values_list('study', 'count')
    )

    if request.user.is_authenticated:
        # Ideally this could be tacked onto studies as an annotation but the
        # generated SQL is extremely inefficient.
        # Map the study id -> num pending tasks a user has to complete on a study
        num_pending_tasks = dict(
            StudyTask.objects.values('study')
            .filter(study__in=studies_page, annotator=request.user, annotation=None)
            .annotate(count=Count(1))
            .values_list('study', 'count')
        )
    else:
        num_pending_tasks = {}

    return render(
        request,
        'studies/study_list.html',
        {
            'studies': studies_page,
            'num_pending_tasks': num_pending_tasks,
            'num_participants': num_participants,
        },
    )


@staff_member_required
def view_mask(request, markup_id):
    markup = get_object_or_404(Markup.objects.values('mask'), pk=markup_id)
    return HttpResponse(markup['mask'], content_type='image/png')


@staff_member_required
def annotation_detail(request, pk):
    annotation = get_object_or_404(
        Annotation.objects.select_related('image', 'study', 'annotator')
        .prefetch_related('markups__feature')
        .prefetch_related('responses__choice')
        .prefetch_related('responses__question'),
        pk=pk,
    )
    return render(
        request,
        'studies/annotation_detail.html',
        {'annotation': annotation},
    )


@permission_or_404('studies.view_study', (Study, 'pk', 'pk'))
def study_detail(request, pk):
    study = get_object_or_404(
        Study.objects.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_annotators=Count('tasks__annotator', distinct=True),
            num_features=Count('features', distinct=True),
            num_questions=Count('questions', distinct=True),
        )
        .select_related('creator')
        .prefetch_related('questions')
        .prefetch_related('features'),
        pk=pk,
    )

    pending_tasks = study.tasks.pending_for_user(request.user)

    return render(
        request, 'studies/study_detail.html', {'study': study, 'pending_tasks': pending_tasks}
    )
