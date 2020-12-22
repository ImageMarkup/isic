from django.contrib import admin
from django.db.models import Count, Exists, OuterRef
from girder_utils.admin import ReadonlyInlineMixin, ReadonlyTabularInline
import nested_admin

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


class FeatureInline(ReadonlyTabularInline):
    model = Study.features.through


class QuestionInline(ReadonlyTabularInline):
    model = Study.questions.through


class MarkupInline(ReadonlyInlineMixin, nested_admin.NestedTabularInline):
    model = Markup


class ResponseInline(ReadonlyInlineMixin, nested_admin.NestedTabularInline):
    model = Response


class AnnotationInline(ReadonlyInlineMixin, nested_admin.NestedTabularInline):
    model = Annotation
    extra = 0
    inlines = [ResponseInline, MarkupInline]


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    search_fields = ['object_id']


@admin.register(Markup)
class MarkupAdmin(admin.ModelAdmin):
    list_display = ['annotation', 'feature', 'present']


@admin.register(QuestionChoice)
class QuestionChoiceAdmin(admin.ModelAdmin):
    list_display = ['question', 'text', 'responded']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(responded=Count('response'))
        return qs

    def responded(self, obj):
        return obj.responded

    responded.admin_order_field = 'responded'


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ['study', 'annotator', 'question', 'choice']

    def study(self, obj):
        return obj.annotation.study

    def annotator(self, obj):
        return obj.annotation.annotator


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    inlines = [ResponseInline, MarkupInline]
    list_display = ['study', 'annotator', 'image']
    list_filter = ['study']
    search_fields = ['annotator__email', 'image__object_id']


@admin.register(StudyTask)
class StudyTaskAdmin(nested_admin.NestedModelAdmin):
    list_display = ['study', 'annotator', 'image', 'complete']
    list_filter = ['study']
    search_fields = ['annotator__email', 'image__object_id', 'study__name']
    inlines = [AnnotationInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(has_annotation=Exists(Annotation.objects.filter(task=OuterRef('pk'))))

    def complete(self, obj):
        return obj.has_annotation

    complete.admin_order_field = 'has_annotation'


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = [
        'created',
        'creator',
        'name',
        'num_tasks',
        'num_responded',
        'num_images',
        'num_features',
        'num_questions',
    ]
    inlines = [QuestionInline, FeatureInline]
    exclude = ['questions', 'features']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_features=Count('features', distinct=True),
            num_questions=Count('questions', distinct=True),
            num_tasks=Count('tasks', distinct=True),
            num_responded=Count('tasks__annotation', distinct=True),
        )

    def num_responded(self, obj):
        return obj.num_responded

    num_responded.admin_order_field = 'num_responded'

    def num_tasks(self, obj):
        return obj.num_tasks

    num_tasks.admin_order_field = 'num_tasks'

    def num_images(self, obj):
        return obj.num_images

    num_images.admin_order_field = 'num_images'

    def num_features(self, obj):
        return obj.num_features

    num_features.admin_order_field = 'num_features'

    def num_questions(self, obj):
        return obj.num_questions

    num_questions.admin_order_field = 'num_questions'


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ['label', 'official']


class QuestionChoiceInline(ReadonlyTabularInline):
    model = QuestionChoice
    fields = ['text']
    extra = 0


class ReferencedStudyInline(ReadonlyTabularInline):
    model = Study.questions.through
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['prompt', 'type', 'required', 'official', 'num_choices', 'used_in']
    inlines = [QuestionChoiceInline, ReferencedStudyInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('choices').annotate(
            num_choices=Count('choices'), used_in=Count('study', distinct=True)
        )

    def num_choices(self, obj):
        return obj.num_choices

    num_choices.admin_order_field = 'num_choices'

    def used_in(self, obj):
        return obj.used_in

    used_in.admin_order_field = 'used_in'
