from django.contrib import admin
from django.db.models import Count, Exists, OuterRef
from girder_utils.admin import ReadonlyInlineMixin, ReadonlyTabularInline
import nested_admin

from isic.studies.models import (
    Annotation,
    Feature,
    Markup,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyTask,
)


class IsStudyTaskCompleteFilter(admin.SimpleListFilter):
    title = 'complete'
    parameter_name = 'complete'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.filter(has_annotation=True)
        elif value == 'no':
            return queryset.exclude(has_annotation=True)
        return queryset


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
    autocomplete_fields = ['annotator', 'image']


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

    @admin.display(ordering='responded')
    def responded(self, obj):
        return obj.responded


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ['study', 'annotator', 'question', 'choice']

    def study(self, obj):
        return obj.annotation.study

    def annotator(self, obj):
        return obj.annotation.annotator


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ['study', 'annotator', 'image']
    list_filter = ['study']
    search_fields = ['annotator__email', 'image__isic__id', 'image__accession__girder_id']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('image__accession', 'image__isic', 'study', 'annotator')

    inlines = [ResponseInline, MarkupInline]
    autocomplete_fields = ['image', 'annotator', 'image', 'task']


@admin.register(StudyTask)
class StudyTaskAdmin(nested_admin.NestedModelAdmin):
    list_display = ['study', 'annotator', 'image', 'complete', 'created']
    list_filter = ['study', IsStudyTaskCompleteFilter]
    search_fields = ['annotator__email', 'image__object_id', 'study__name']

    autocomplete_fields = ['image', 'annotator', 'image']
    readonly_fields = ['created']
    inlines = [AnnotationInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(has_annotation=Exists(Annotation.objects.filter(task=OuterRef('pk'))))

    @admin.display(ordering='has_annotation', boolean=True)
    def complete(self, obj):
        return obj.has_annotation


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = [
        'created',
        'creator',
        'name',
        'public',
        'num_tasks',
        'num_responded',
        'num_images',
        'num_features',
        'num_questions',
    ]
    list_filter = ['public']

    exclude = ['questions', 'features']
    inlines = [QuestionInline, FeatureInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_features=Count('features', distinct=True),
            num_questions=Count('questions', distinct=True),
            num_tasks=Count('tasks', distinct=True),
            num_responded=Count('tasks__annotation', distinct=True),
        )

    @admin.display(ordering='num_responded')
    def num_responded(self, obj):
        return obj.num_responded

    @admin.display(ordering='num_tasks')
    def num_tasks(self, obj):
        return obj.num_tasks

    @admin.display(ordering='num_images')
    def num_images(self, obj):
        return obj.num_images

    @admin.display(ordering='num_features')
    def num_features(self, obj):
        return obj.num_features

    @admin.display(ordering='num_questions')
    def num_questions(self, obj):
        return obj.num_questions


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

    @admin.display(ordering='num_choices')
    def num_choices(self, obj):
        return obj.num_choices

    @admin.display(ordering='used_in')
    def used_in(self, obj):
        return obj.used_in
