from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, User
from django.db import transaction
from django.db.models.expressions import F
from django.http import HttpRequest
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from django.utils import timezone

from isic.core.models.image import Image
from isic.core.permissions import needs_object_permission
from isic.studies.forms import StudyTaskForm
from isic.studies.models import Annotation, Question, Study, StudyTask


def maybe_redirect_to_next_study_task(request: HttpRequest, study: Study):
    next_task = study.tasks.pending().for_user(request.user).random_next()

    if not next_task:
        messages.add_message(
            request, messages.SUCCESS, "You've completed all tasks for this study."
        )
        return HttpResponseRedirect(reverse("studies/study-detail", args=[study.pk]))

    return HttpResponseRedirect(reverse("studies/study-task-detail", args=[next_task.pk]))


@needs_object_permission("studies.view_study_task", (StudyTask, "pk", "pk"))
def study_task_detail(request, pk):
    study_task: StudyTask = get_object_or_404(
        StudyTask.objects.select_related("annotator", "image", "image__accession", "study"),
        pk=pk,
    )
    questions = (
        study_task.study.questions.prefetch_related("choices")
        .annotate(required=F("study_questions__required"))  # required for StudyTaskForm
        .order_by("study_questions__order")
        .all()
    )

    if study_task.complete:
        return maybe_redirect_to_next_study_task(request, study_task.study)

    if request.method == "POST":
        form = StudyTaskForm(
            request.POST, questions=questions, study=study_task.study, user=request.user
        )
        if form.is_valid():
            with transaction.atomic():
                annotation = Annotation.objects.create(
                    study=study_task.study,
                    image=study_task.image,
                    task=study_task,
                    annotator=request.user,
                    start_time=form.cleaned_data["start_time"],
                )

                del form.cleaned_data["start_time"]

                # TODO: markups, one day?
                for question_pk, response_value in form.cleaned_data.items():
                    if response_value == "":
                        continue
                    question = form.questions[int(question_pk)]
                    if question.type == Question.QuestionType.NUMBER:
                        annotation.responses.create(
                            question=question,
                            value=int(response_value)
                            if float(response_value).is_integer()
                            else float(response_value),
                        )
                    elif question.type == Question.QuestionType.MULTISELECT:
                        choice_pks = [int(pk) for pk in response_value]
                        annotation.responses.create(
                            question=question, value={"choices": choice_pks}
                        )
                    else:
                        choices = {x.pk: x for x in question.choices.all()}
                        annotation.responses.create(
                            question=question, choice=choices[int(response_value)]
                        )

            return maybe_redirect_to_next_study_task(request, study_task.study)
    else:
        form = StudyTaskForm(
            initial={"start_time": timezone.now()},
            questions=questions,
            study=study_task.study,
            user=request.user,
        )

    context = {
        "study_task": study_task,
        "form": form,
        "diagnosis_only_form": questions.count() == 1
        and questions.first().type == Question.QuestionType.DIAGNOSIS,
        "just_completed_task": StudyTask.objects.for_user(request.user).just_completed().last(),
        "tasks_remaining": study_task.study.tasks.pending().for_user(request.user).count(),
        "preview_mode": False,
        "include_metadata": False,
    }

    return render(request, "studies/study_task_detail.html", context)


@needs_object_permission("studies.view_study", (Study, "pk", "pk"))
def study_task_detail_preview(request, pk):
    study = get_object_or_404(Study, pk=pk)
    image = (
        Image.objects.select_related("accession")
        .filter(pk__in=study.tasks.values("image"))
        .order_by("?")
        .first()
    )

    # note: a studytask can't be built with an AnonymousUser, so use a dummy User object
    annotator = request.user if not isinstance(request.user, AnonymousUser) else User()
    # note: this intentionally builds but doesn't create a study task
    study_task = StudyTask(study=study, annotator=annotator, image=image)

    questions = (
        study_task.study.questions.prefetch_related("choices")
        .annotate(required=F("study_questions__required"))  # required for StudyTaskForm
        .order_by("study_questions__order")
        .all()
    )

    form = StudyTaskForm(
        initial={"start_time": timezone.now()}, questions=questions, study=study, user=request.user
    )

    return render(
        request,
        "studies/study_task_detail.html",
        {
            "study_task": study_task,
            "form": form,
            "diagnosis_only_form": questions.count() == 1
            and questions.first().type == Question.QuestionType.DIAGNOSIS,
            "just_completed_task": None,
            "preview_mode": True,
            "include_metadata": False,
        },
    )
