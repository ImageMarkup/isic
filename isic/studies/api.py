from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from isic.auth import IsAuthenticated, IsStaff
from isic.core.pagination import paginate
from isic.studies.models import Annotation, Feature, QuestionChoice, Study, StudyTask
from isic.studies.models.study_question import StudyQuestion


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = ["id", "study", "image", "task", "annotator"]


@api_view(["GET"])
@permission_classes([IsStaff])
def annotation_list(request):
    return paginate(request, Annotation.objects.all(), AnnotationSerializer)


@api_view(["GET"])
@permission_classes([IsStaff])
def annotation_detail(request, id: int):
    return Response(AnnotationSerializer(get_object_or_404(Annotation, id=id)).data)


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ["id", "required", "name", "official"]


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ["id", "question", "text"]


class StudyQuestionSerializer(serializers.ModelSerializer):
    """Serialize a question along with whether its study requires it."""

    class Meta:
        model = StudyQuestion
        fields = ["id", "type", "prompt", "official", "choices", "required"]

    id = serializers.IntegerField(source="question.id")
    type = serializers.CharField(source="question.type")
    prompt = serializers.CharField(source="question.prompt")
    official = serializers.BooleanField(source="question.official")
    choices = QuestionChoiceSerializer(source="question.choices", many=True)


class StudySerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = ["id", "created", "creator", "name", "description", "features", "questions"]

    features = FeatureSerializer(many=True)
    questions = StudyQuestionSerializer(source="study_questions", many=True)


default_study_qs = Study.objects.prefetch_related("features", "study_questions__question__choices")


@api_view(["GET"])
@permission_classes([IsStaff])
def study_list(request):
    return paginate(request, default_study_qs, StudySerializer)


@api_view(["GET"])
@permission_classes([IsStaff])
def study_detail(request, id: int):
    return Response(StudySerializer(get_object_or_404(default_study_qs, id=id)).data)


class StudyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyTask
        fields = ["id", "study", "image", "annotator", "complete"]

    complete = serializers.BooleanField()


@api_view(["GET"])
@permission_classes([IsStaff])
def study_task_list(request):
    return paginate(request, StudyTask.objects.prefetch_related("annotation"), StudyTaskSerializer)


@api_view(["GET"])
@permission_classes([IsStaff])
def study_task_detail(request, id: int):
    return Response(StudyTaskSerializer(get_object_or_404(StudyTask, id=id)).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def study_task_undo(request, id: int):
    study_task: StudyTask = get_object_or_404(
        StudyTask.objects.select_related("annotation").for_user(request.user).just_completed(),
        pk=id,
    )

    # this cascading deletes the response/markup
    study_task.annotation.delete()

    return Response({"success": True})


annotation_urlpatterns = [
    path("", annotation_list, name="annotation_list"),
    path("<int:id>/", annotation_detail, name="annotation_detail"),
]

study_urlpatterns = [
    path("", study_list, name="study_list"),
    path("<int:id>/", study_detail, name="study_detail"),
]

study_task_urlpatterns = [
    path("", study_task_list, name="study_task_list"),
    path("<int:id>/", study_task_detail, name="study_task_detail"),
    path("<int:id>/undo/", study_task_undo, name="study_task_undo"),
]
