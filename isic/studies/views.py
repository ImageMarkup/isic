from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from rest_framework import viewsets
from django.core.paginator import Paginator

from isic.studies.models import *
from isic.studies.serializers import *


class StudyTaskViewSet(viewsets.ModelViewSet):
    serializer_class = StudyTaskSerializer
    queryset = StudyTask.objects.all()


class StudyViewSet(viewsets.ModelViewSet):
    serializer_class = StudySerializer
    queryset = Study.objects.all()


class AnnotationViewSet(viewsets.ModelViewSet):
    serializer_class = AnnotationSerializer
    queryset = Annotation.objects.all()


def study_list(request):
    studies = get_objects_for_user(
        request.user, 'studies.view_study'
    )
    return render(request, 'studies/study_list.html', {'studies': studies})


def view_mask(request, markup_id):
    markup = get_object_or_404(Markup, pk=markup_id)
    return HttpResponse(markup.mask, content_type='image/png')


class AnnotationDetailView(DetailView):
    def get_queryset(self):
        return (
            Annotation.objects.select_related('image', 'study', 'annotator')
            .prefetch_related('markups__feature')
            .prefetch_related('responses__choice')
            .prefetch_related('responses__question')
            .filter(pk=self.kwargs.get('pk'))
        )


class StudyDetailView(DetailView):
    model = Study

    def get_context_data(self, **kwargs):
        responses = (
            Annotation.objects.filter(study=self.object)
            .select_related('annotator', 'image')
            .order_by('created')
        )
        paginator = Paginator(responses, 50)
        responses_page = paginator.get_page(self.request.GET.get('page'))
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'features': self.object.features.order_by('name').all(),
                'questions': self.object.questions.all(),
                'num_images': self.object.tasks.values('image').distinct().count(),
                'num_annotators': self.object.tasks.values('annotator').distinct().count(),
                'num_tasks': self.object.tasks.count(),
                'responses': responses_page,
                'num_responses': Annotation.objects.filter(study=self.object).count(),
            }
        )
        return context


class QuestionListView(ListView):
    model = Question


class FeatureListView(ListView):
    model = Feature

class CreateStudyView(CreateView):
    model = Study
    fields = ['name', 'description', 'features', 'questions']
    template_name = 'studies/study_create.html'

    def get_success_url(self):
        return reverse('study-detail', args=[self.object.id])

    def form_valid(self, form):
        form.instance.creator = self.request.user
        return super().form_valid(form)
