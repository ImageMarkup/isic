from collections import defaultdict
from datetime import UTC, datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.expressions import F
from django.db.models.query import Prefetch
from django.db.models.query_utils import Q
from django.forms.formsets import formset_factory
from django.http import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls.base import reverse
from django.utils import timezone

from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.templatetags.display import user_nicename
from isic.studies.forms import (
    BaseStudyForm,
    CustomQuestionForm,
    OfficialQuestionForm,
    StudyEditForm,
    StudyTaskForm,
)
from isic.studies.models import (
    Annotation,
    Markup,
    Question,
    QuestionChoice,
    Study,
    StudyTask,
)
from isic.studies.services import study_create, study_update
from isic.studies.tasks import populate_study_tasks_task


def study_list(request):
    studies = get_visible_objects(
        request.user,
        "studies.view_study",
        Study.objects.select_related("creator").distinct().order_by("-created"),
    )
    paginator = Paginator(studies, 10)
    studies_page = paginator.get_page(request.GET.get("page"))

    num_participants = defaultdict(
        int,
        StudyTask.objects.values("study")
        .filter(study__in=studies_page)
        .annotate(count=Count("annotator", distinct=True))
        .values_list("study", "count"),
    )

    num_pending_tasks = defaultdict(int)
    num_completed_tasks = defaultdict(int)

    if request.user.is_authenticated:
        # Ideally this could be tacked onto studies as an annotation but the
        # generated SQL is extremely inefficient.
        # Map the study id -> num pending tasks a user has to complete on a study
        num_pending_tasks.update(
            StudyTask.objects.values("study")
            .filter(study__in=studies_page, annotator=request.user, annotation=None)
            .annotate(count=Count(1))
            .values_list("study", "count"),
        )
        num_completed_tasks.update(
            StudyTask.objects.values("study")
            .filter(study__in=studies_page, annotator=request.user)
            .exclude(annotation=None)
            .annotate(count=Count(1))
            .values_list("study", "count"),
        )

    return render(
        request,
        "studies/study_list.jinja",
        {
            "studies": studies_page,
            "num_pending_tasks": num_pending_tasks,
            "num_completed_tasks": num_completed_tasks,
            "num_participants": num_participants,
        },
    )


@login_required
@transaction.atomic()
def study_create_view(request):
    OfficialQuestionFormSet = formset_factory(  # noqa: N806
        OfficialQuestionForm, extra=0
    )
    CustomQuestionFormSet = formset_factory(CustomQuestionForm, extra=0)  # noqa: N806

    visible_collections = get_visible_objects(request.user, "core.view_collection").order_by("name")

    base_form = BaseStudyForm(
        request.POST or None, user=request.user, collections=visible_collections
    )
    custom_question_formset = CustomQuestionFormSet(request.POST or None, prefix="custom")
    official_question_formset = OfficialQuestionFormSet(request.POST or None, prefix="official")

    if request.method == "POST" and (
        base_form.is_valid()
        and custom_question_formset.is_valid()
        and official_question_formset.is_valid()
    ):
        study = study_create(
            creator=request.user,
            owners=[request.user],
            attribution=base_form.cleaned_data["attribution"],
            name=base_form.cleaned_data["name"],
            description=base_form.cleaned_data["description"],
            collection=base_form.cleaned_data["collection"],
            public=base_form.cleaned_data["public"],
        )

        for question in official_question_formset.cleaned_data:
            study.questions.add(
                Question.objects.get(pk=question["question_id"]),
                through_defaults={"required": question["required"]},
            )

        for custom_question in custom_question_formset.cleaned_data:
            q = Question.objects.create(prompt=custom_question["prompt"], official=False)
            for choice in custom_question["choices"]:
                QuestionChoice.objects.create(question=q, text=choice)
            study.questions.add(q, through_defaults={"required": custom_question["required"]})

        messages.add_message(request, messages.INFO, "Creating study, this may take a few minutes.")
        populate_study_tasks_task.delay_on_commit(study.pk, base_form.cleaned_data["annotators"])

        return HttpResponseRedirect(reverse("study-detail", args=[study.pk]))

    questions = [
        {"id": q.id, "prompt": q.prompt, "choices_for_display": ", ".join(q.choices_for_display())}
        for q in Question.objects.filter(official=True)
        .prefetch_related("choices")
        .order_by("prompt")
    ]

    return render(
        request,
        "studies/study_create.html",
        {
            "existing_questions": questions,
            "visible_collections": visible_collections,
            "base_form": base_form,
            "official_question_formset": official_question_formset,
            "custom_question_formset": custom_question_formset,
        },
    )


@needs_object_permission("studies.edit_study", (Study, "pk", "pk"))
def study_edit(request, pk):
    study = get_object_or_404(Study, pk=pk)
    form = StudyEditForm(
        request.POST or {key: getattr(study, key) for key in ["name", "description"]}
    )

    if request.method == "POST" and form.is_valid():
        try:
            study_update(study=study, **form.cleaned_data)
        except ValidationError as e:
            messages.add_message(request, messages.ERROR, e.message)
        else:
            return HttpResponseRedirect(reverse("study-detail", args=[study.pk]))

    return render(request, "studies/study_edit.html", {"form": form, "study": study})


@staff_member_required
def view_mask(request, markup_id):
    markup = get_object_or_404(Markup.objects.values("mask"), pk=markup_id)
    return HttpResponseRedirect(markup["mask"].url)


@staff_member_required
def annotation_detail(request, pk):
    annotation = get_object_or_404(
        Annotation.objects.select_related("image", "study", "annotator")
        .prefetch_related("markups__feature")
        .prefetch_related("responses__choice")
        .prefetch_related("responses__question"),
        pk=pk,
    )
    return render(
        request,
        "studies/annotation_detail.html",
        {"annotation": annotation},
    )


@needs_object_permission("studies.view_study", (Study, "pk", "pk"))
def study_detail(request, pk):
    ctx = {"can_edit": request.user.has_perm("studies.edit_study", Study(pk=pk))}
    ctx["study"] = get_object_or_404(
        Study.objects.annotate(
            num_annotators=Count("tasks__annotator", distinct=True),
            num_features=Count("features", distinct=True),
            num_questions=Count("questions", distinct=True),
        )
        .select_related("creator")
        .prefetch_related(
            # the entire point of this prefetch is to select the questions ordered by the
            # StudyQuestion.order field. This is pretty contrived but there doesn't appear
            # to be an easier way.
            Prefetch(
                "questions",
                queryset=Question.objects.prefetch_related("choices")
                .filter(studyquestion__study_id=pk)
                .order_by("studyquestion__order", "prompt"),
            )
        )
        .prefetch_related("features"),
        pk=pk,
    )

    # Note: there is no permission checking here because access to the study means
    # access to the images when viewing the study. See Study.public comment as well.
    images = Image.objects.filter(pk__in=ctx["study"].tasks.values("image").distinct())
    paginator = Paginator(images.select_related("accession"), 30)
    ctx["num_images"] = images.count()
    ctx["images"] = paginator.get_page(request.GET.get("page"))

    if request.user.is_authenticated:
        ctx["pending_tasks"] = ctx["study"].tasks.pending().for_user(request.user)
        ctx["next_task"] = ctx["pending_tasks"].random_next()

    annotator_counts = list(
        ctx["study"]
        .tasks.values("annotator")
        .annotate(completed=Count("pk", filter=~Q(annotation=None)), total=Count("pk"))
        .order_by("annotator__last_name", "annotator__first_name")
    )
    annotators = list(
        User.objects.select_related("profile")
        .filter(pk__in=[x["annotator"] for x in annotator_counts])
        .order_by("last_name", "first_name")
    )
    # TODO: Fix brittleness - both of the lists have to be ordered by the same thing for this to
    # work.
    ctx["annotators"] = zip(annotators, annotator_counts, strict=False)

    # TODO: create a formal permission for this?
    # Using view_study_results would make all public studies show real user names.
    ctx["show_real_names"] = request.user.is_staff or request.user in ctx["study"].owners.all()

    # passing request.user to a queryset requires an authenticated user, so wrap
    # the entire block in request.user.is_authenticated check anyway.
    if request.user.is_authenticated and (
        request.user.is_staff
        or request.user in ctx["study"].owners.all()
        or ctx["study"].tasks.filter(annotator=request.user).exists()
    ):
        ctx["owners"] = [user_nicename(u) for u in ctx["study"].owners.all()]

    return render(request, "studies/study_detail.html", ctx)


@needs_object_permission("studies.view_study_results", (Study, "pk", "pk"))
def study_responses_csv(request, pk):
    study: Study = get_object_or_404(Study, pk=pk)
    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{slugify(study.name)}_responses_{current_time}.csv"'
    )
    study.write_responses_csv(response)
    return response


def maybe_redirect_to_next_study_task(request: HttpRequest, study: Study):
    next_task = study.tasks.pending().for_user(request.user).random_next()

    if not next_task:
        messages.add_message(
            request, messages.SUCCESS, "You've completed all tasks for this study."
        )
        return HttpResponseRedirect(reverse("study-detail", args=[study.pk]))

    return HttpResponseRedirect(reverse("study-task-detail", args=[next_task.pk]))


@needs_object_permission("studies.view_study_task", (StudyTask, "pk", "pk"))
def study_task_detail(request, pk):
    study_task: StudyTask = get_object_or_404(
        StudyTask.objects.select_related("annotator", "image", "study"),
        pk=pk,
    )
    questions = (
        study_task.study.questions.prefetch_related("choices")
        .annotate(required=F("studyquestion__required"))  # required for StudyTaskForm
        .order_by("studyquestion__order")
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
                for question_pk, choice_pk in form.cleaned_data.items():
                    if choice_pk == "":  # ignore optional questions
                        continue
                    question = form.questions[int(question_pk)]
                    choices = {x.pk: x for x in question.choices.all()}
                    annotation.responses.create(question=question, choice=choices[int(choice_pk)])

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
    }

    return render(request, "studies/study_task_detail.html", context)


@needs_object_permission("studies.view_study", (Study, "pk", "pk"))
def study_task_detail_preview(request, pk):
    study = get_object_or_404(Study, pk=pk)
    image = Image.objects.filter(pk__in=study.tasks.values("image")).order_by("?").first()

    # note: a studytask can't be built with an AnonymousUser, so use a dummy User object
    annotator = request.user if not isinstance(request.user, AnonymousUser) else User()
    # note: this intentionally builds but doesn't create a study task
    study_task = StudyTask(study=study, annotator=annotator, image=image)

    questions = (
        study_task.study.questions.prefetch_related("choices")
        .annotate(required=F("studyquestion__required"))  # required for StudyTaskForm
        .order_by("studyquestion__order")
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
            "preview_mode": True,
        },
    )
