from rest_framework import serializers

from isic.studies.models import Annotation, Feature, Question, QuestionChoice, Study, StudyTask


class StudyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyTask
        fields = ['id', 'study', 'image', 'complete', 'annotator']


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = ['id', 'study', 'image', 'task', 'annotator']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'required', 'name', 'official']


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ['id', 'question', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    choices = QuestionChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'required', 'type', 'prompt', 'official', 'choices']


class StudySerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True)
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Study
        fields = ['id', 'created', 'creator', 'name', 'description', 'features', 'questions']
