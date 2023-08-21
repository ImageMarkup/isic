from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, ModelSchema, Router
from ninja.pagination import paginate

from isic.core.pagination import CursorPagination
from isic.core.permissions import SessionAuthStaffUser
from isic.studies.models import Annotation, Feature, Question, QuestionChoice, Study, StudyTask

annotation_router = Router()
study_router = Router()
study_task_router = Router()


class AnnotationOut(ModelSchema):
    class Config:
        model = Annotation
        model_fields = ["id", "study", "image", "task", "annotator"]


@annotation_router.get(
    "/", response=list[AnnotationOut], include_in_schema=False, auth=SessionAuthStaffUser
)
@paginate(CursorPagination)
def annotation_list(request: HttpRequest):
    return Annotation.objects.all()


@annotation_router.get(
    "/{id}/", response=AnnotationOut, include_in_schema=False, auth=SessionAuthStaffUser
)
def annotation_detail(request: HttpRequest, id: int):
    return get_object_or_404(Annotation, id=id)


class FeatureOut(ModelSchema):
    class Config:
        model = Feature
        model_fields = ["id", "required", "name", "official"]


class QuestionChoiceOut(ModelSchema):
    class Config:
        model = QuestionChoice
        model_fields = ["id", "question", "text"]


class QuestionOut(ModelSchema):
    choices: list[QuestionChoiceOut]
    required: bool = Field(alias="required")

    class Config:
        model = Question
        model_fields = ["id", "type", "prompt", "official"]


class StudyOut(ModelSchema):
    class Config:
        model = Study
        model_fields = ["id", "created", "creator", "name", "description"]

    features: list[FeatureOut]
    questions: list[QuestionOut] = Field(alias="questions")

    @staticmethod
    def resolve_questions(study: Study) -> list[QuestionOut]:
        # Is there a better way with ninja to add fields from the M2M through-table?
        vals = []
        for study_question in study.studyquestion_set.all():
            study_question.question.required = study_question.required
            question_out = QuestionOut.from_orm(study_question.question)
            vals.append(question_out)
        return vals


@study_router.get("/", response=list[StudyOut], include_in_schema=False, auth=SessionAuthStaffUser)
@paginate(CursorPagination)
def study_list(request: HttpRequest):
    return Study.objects.prefetch_related("features", "studyquestion_set__question__choices")


@study_router.get("/{id}/", response=StudyOut, include_in_schema=False, auth=SessionAuthStaffUser)
def study_detail(request: HttpRequest, id: int):
    return get_object_or_404(Study, id=id)


class StudyTaskOut(ModelSchema):
    class Config:
        model = StudyTask
        model_fields = ["id", "study", "image", "annotator"]

    complete: bool = Field(alias="complete")


@study_task_router.get(
    "/", response=list[StudyTaskOut], include_in_schema=True, auth=SessionAuthStaffUser
)
@paginate(CursorPagination)
def study_task_list(request: HttpRequest):
    return StudyTask.objects.prefetch_related("annotation")


@study_task_router.get(
    "/{id}/", response=StudyTaskOut, include_in_schema=False, auth=SessionAuthStaffUser
)
def study_task_detail(request: HttpRequest, id: int):
    return get_object_or_404(StudyTask, id=id)
