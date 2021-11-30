from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.query import Prefetch
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import get_visible_objects, permission_or_404
from isic.studies.forms import StudyTaskForm
from isic.studies.models import Annotation, Markup, Question, Response, Study, StudyTask


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
        num_completed_tasks = dict(
            StudyTask.objects.values('study')
            .filter(study__in=studies_page, annotator=request.user)
            .exclude(annotation=None)
            .annotate(count=Count(1))
            .values_list('study', 'count')
        )
    else:
        num_pending_tasks = None
        num_completed_tasks = None

    return render(
        request,
        'studies/study_list.html',
        {
            'studies': studies_page,
            'num_pending_tasks': num_pending_tasks,
            'num_completed_tasks': num_completed_tasks,
            'num_participants': num_participants,
        },
    )


@staff_member_required
def view_mask(request, markup_id):
    markup = get_object_or_404(Markup.objects.values('mask'), pk=markup_id)
    return HttpResponseRedirect(markup['mask'].url)


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
    ctx = {}
    ctx['study'] = get_object_or_404(
        Study.objects.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_annotators=Count('tasks__annotator', distinct=True),
            num_features=Count('features', distinct=True),
            num_questions=Count('questions', distinct=True),
        )
        .select_related('creator')
        .prefetch_related(
            # the entire point of this prefetch is to select the questions ordered by the
            # StudyQuestion.order field. This is pretty contrived but there doesn't appear
            # to be an easier way.
            Prefetch(
                'questions',
                queryset=Question.objects.filter(studyquestion__study_id=pk).order_by(
                    'studyquestion__order', 'prompt'
                ),
            )
        )
        .prefetch_related('features'),
        pk=pk,
    )
    ctx['pending_tasks'] = ctx['study'].tasks.pending().for_user(request.user)
    ctx['next_task'] = ctx['pending_tasks'].random_next()

    visible_annotations = get_visible_objects(
        request.user, 'studies.view_annotation', ctx['study'].annotations.all()
    )
    ctx['responses'] = (
        Response.objects.select_related(
            'annotation', 'annotation__annotator', 'annotation__image', 'question', 'choice'
        )
        .filter(annotation__in=visible_annotations)
        .order_by('annotation__image', 'annotation__annotator')
    )
    paginator = Paginator(ctx['responses'], 10)
    ctx['responses'] = paginator.get_page(request.GET.get('page'))

    return render(request, 'studies/study_detail.html', ctx)


def maybe_redirect_to_next_study_task(user: User, study: Study):
    next_task = study.tasks.pending().for_user(user).random_next()

    if not next_task:
        return HttpResponseRedirect(reverse('study-detail', args=[study.pk]))
    else:
        return HttpResponseRedirect(reverse('study-task-detail', args=[next_task.pk]))


@permission_or_404('studies.view_study_task', (StudyTask, 'pk', 'pk'))
def study_task_detail(request, pk):
    study_task: StudyTask = get_object_or_404(
        StudyTask.objects.select_related('annotator', 'image', 'study'),
        pk=pk,
    )
    questions = (
        study_task.study.questions.prefetch_related('choices')
        .order_by('studyquestion__order')
        .all()
    )

    if study_task.complete:
        return maybe_redirect_to_next_study_task(request.user, study_task.study)

    if request.method == 'POST':
        form = StudyTaskForm(request.POST, questions=questions)
        if form.is_valid():
            with transaction.atomic():
                annotation = Annotation.objects.create(
                    study=study_task.study,
                    image=study_task.image,
                    task=study_task,
                    annotator=request.user,
                )

                # TODO: markups, one day?
                for question_pk, choice_pk in form.cleaned_data.items():
                    if choice_pk == '':  # ignore optional questions
                        continue
                    question = form.questions[int(question_pk)]
                    choices = {x.pk: x for x in question.choices.all()}
                    annotation.responses.create(question=question, choice=choices[int(choice_pk)])

            return maybe_redirect_to_next_study_task(request.user, study_task.study)
    else:
        form = StudyTaskForm(questions=questions)

    context = {
        'study_task': study_task,
        'form': form,
        'tasks_remaining': study_task.study.tasks.pending().for_user(request.user).count(),
    }

    return render(request, 'studies/study_task_detail.html', context)
