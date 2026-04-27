from datetime import UTC, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.query import Prefetch
from django.db.models.query_utils import Q
from django.forms.formsets import formset_factory
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls.base import reverse

from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.templatetags.display import user_nicename
from isic.core.utils.csv import EscapingDictWriter
from isic.studies.forms import (
    BaseStudyForm,
    CustomQuestionForm,
    OfficialQuestionForm,
    StudyAddAnnotatorsForm,
    StudyEditForm,
)
from isic.studies.models import Question, QuestionChoice, Response, Study, StudyTask
import isic.studies.services as study_services
from isic.studies.tasks import populate_study_tasks_task


def study_list(request):
    studies = get_visible_objects(
        request.user,
        "studies.view_study",
        Study.objects.select_related("creator").distinct().order_by("-created"),
    )
    paginator = Paginator(studies, 10)
    studies_page = paginator.get_page(request.GET.get("page"))

    num_participants = dict(
        StudyTask.objects.values("study")
        .filter(study__in=studies_page)
        .annotate(count=Count("annotator", distinct=True))
        .values_list("study", "count")
    )

    if request.user.is_authenticated:
        # Ideally this could be tacked onto studies as an annotation but the
        # generated SQL is extremely inefficient.
        # Map the study id -> num pending tasks a user has to complete on a study
        num_pending_tasks = dict(
            StudyTask.objects.values("study")
            .filter(study__in=studies_page, annotator=request.user, annotation=None)
            .annotate(count=Count(1))
            .values_list("study", "count")
        )
        num_completed_tasks = dict(
            StudyTask.objects.values("study")
            .filter(study__in=studies_page, annotator=request.user)
            .exclude(annotation=None)
            .annotate(count=Count(1))
            .values_list("study", "count")
        )
    else:
        num_pending_tasks = {}
        num_completed_tasks = {}

    return render(
        request,
        "studies/study_list.html",
        {
            "studies": studies_page,
            "num_pending_tasks": num_pending_tasks,
            "num_completed_tasks": num_completed_tasks,
            "num_participants": num_participants,
        },
    )


@login_required
@transaction.atomic()
def study_create(request):
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
        study = study_services.study_create(
            creator=request.user,
            owners=[request.user],
            attribution=base_form.cleaned_data["attribution"],
            name=base_form.cleaned_data["name"],
            description=base_form.cleaned_data["description"],
            collection=base_form.cleaned_data["collection"],
            public=base_form.cleaned_data["public"],
            zoomable=base_form.cleaned_data["zoomable"],
        )

        for question in official_question_formset.cleaned_data:
            study.questions.add(
                Question.objects.get(pk=question["question_id"]),
                through_defaults={"required": question["required"]},
            )

        for custom_question in custom_question_formset.cleaned_data:
            q = Question.objects.create(
                prompt=custom_question["prompt"],
                type=custom_question["question_type"],
                official=False,
            )
            for choice in custom_question["choices"]:
                QuestionChoice.objects.create(question=q, text=choice)
            study.questions.add(q, through_defaults={"required": custom_question["required"]})

        messages.add_message(request, messages.INFO, "Creating study, this may take a few minutes.")
        populate_study_tasks_task.delay_on_commit(study.pk, base_form.cleaned_data["annotators"])

        return HttpResponseRedirect(reverse("studies/study-detail", args=[study.pk]))

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
        request.POST or {key: getattr(study, key) for key in ["name", "description", "zoomable"]}
    )

    if request.method == "POST" and form.is_valid():
        try:
            study_services.study_update(study=study, **form.cleaned_data)
        except ValidationError as e:
            messages.add_message(request, messages.ERROR, e.message)
        else:
            return HttpResponseRedirect(reverse("studies/study-detail", args=[study.pk]))

    return render(request, "studies/study_edit.html", {"form": form, "study": study})


@needs_object_permission("studies.edit_study", (Study, "pk", "pk"))
def study_add_annotators(request, pk):
    study = get_object_or_404(Study, pk=pk)

    existing_annotators = (
        User.objects.filter(pk__in=study.tasks.values("annotator").distinct())
        .select_related("profile")
        .order_by("last_name", "first_name")
    )
    existing_user_pks = set(existing_annotators.values_list("pk", flat=True))

    show_real_names = request.user.is_staff or request.user in study.owners.all()

    if request.method == "POST":
        form = StudyAddAnnotatorsForm(request.POST)
        if form.is_valid():
            additional_user_pks = form.cleaned_data["annotators"]
            new_user_pks = [pk for pk in additional_user_pks if pk not in existing_user_pks]

            if new_user_pks:
                populate_study_tasks_task.delay_on_commit(study.pk, new_user_pks)
                messages.add_message(
                    request, messages.INFO, "Adding annotator(s), this may take a few minutes."
                )
            else:
                messages.add_message(
                    request, messages.WARNING, "All specified users are already annotators."
                )

            return HttpResponseRedirect(reverse("studies/study-detail", args=[study.pk]))
    else:
        form = StudyAddAnnotatorsForm()

    return render(
        request,
        "studies/study_add_annotators.html",
        {
            "study": study,
            "form": form,
            "existing_annotators": existing_annotators,
            "show_real_names": show_real_names,
        },
    )


@needs_object_permission("studies.view_study", (Study, "pk", "pk"))
def study_detail(request, pk):
    ctx = {
        "can_edit": request.user.has_perm("studies.edit_study", Study(pk=pk)),
        "pending_tasks": None,
        "next_task": None,
        "owners": None,
    }
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
                .filter(study_questions__study_id=pk)
                .order_by("study_questions__order", "prompt"),
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
    study_responses = Response.objects.filter(annotation__study=study)

    http_response = HttpResponse(content_type="text/csv")
    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    http_response["Content-Disposition"] = (
        f'attachment; filename="{slugify(study.name)}_responses_{current_time}.csv"'
    )

    fieldnames = [
        "image",
        "annotator",
        "annotation_duration",
        "question",
        "question_type",
        "answer",
    ]
    writer = EscapingDictWriter(http_response, fieldnames)
    writer.writeheader()
    for study_responses_data in study_responses.for_display():
        writer.writerow({field: study_responses_data[field] for field in fieldnames})

    return http_response
