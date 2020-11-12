from django.contrib import admin
from django.db.models import Count

from isic.studies.models import (
    Annotation,
    Feature,
    Image,
    Markup,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyTask,
)


class FeatureInline(admin.TabularInline):
    model = Study.features.through


class QuestionInline(admin.TabularInline):
    model = Study.questions.through


class MarkupInline(admin.TabularInline):
    model = Markup


class ResponseInline(admin.TabularInline):
    model = Response


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    pass


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    inlines = [ResponseInline, MarkupInline]


@admin.register(StudyTask)
class StudyTaskAdmin(admin.ModelAdmin):
    list_display = ['study', 'annotator', 'image', 'complete']
    list_filter = ['study']


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ['created', 'name', 'num_images', 'num_features', 'num_questions']
    inlines = [QuestionInline, FeatureInline]
    exclude = ['questions', 'features']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_features=Count('features', distinct=True),
            num_questions=Count('questions', distinct=True),
        )

    def num_images(self, obj):
        return obj.num_images

    def num_features(self, obj):
        return obj.num_features

    def num_questions(self, obj):
        return obj.num_questions


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    pass


class QuestionChoiceInline(admin.TabularInline):
    model = QuestionChoice
    fields = ['text']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['prompt', 'type', 'required', 'official', 'num_choices']
    inlines = [QuestionChoiceInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('choices')

    def num_choices(self, obj):
        return obj.choices.count()
