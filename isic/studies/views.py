from django.core.paginator import Paginator
from django.http import HttpResponse
from django.http.response import Http404
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from django.views.generic.edit import CreateView
from guardian.decorators import permission_required_or_404
from guardian.shortcuts import get_objects_for_user

from isic.studies.models import Annotation, Markup, Study


def study_list(request):
    studies = get_objects_for_user(request.user, 'studies.view_study')
    return render(request, 'studies/study_list.html', {'studies': studies})


def view_mask(request, markup_id):
    markup = get_object_or_404(Markup, pk=markup_id)

    if not request.user.has_perm('studies.view_annotation', markup.annotation):
        return Http404()

    return HttpResponse(markup.mask, content_type='image/png')


@permission_required_or_404(
    'studies.view_annotation', (Annotation, 'pk', 'pk'), accept_global_perms=True
)
def annotation_detail(request, pk):
    return render(
        request,
        'studies/annotation_detail.html',
        {
            'annotation': Annotation.objects.select_related('image', 'study', 'annotator')
            .prefetch_related('markups__feature')
            .prefetch_related('responses__choice')
            .prefetch_related('responses__question')
            .get(pk=pk)
        },
    )


# TODO: email anonymization
@permission_required_or_404('studies.view_study', (Study, 'pk', 'pk'), accept_global_perms=True)
def study_detail(request, pk):
    study = get_object_or_404(Study, pk=pk)
    responses = (
        Annotation.objects.filter(study=study)
        .select_related('annotator', 'image')
        .order_by('created')
    )
    paginator = Paginator(responses, 50)
    responses_page = paginator.get_page(request.GET.get('page'))
    context = {
        'study': study,
        'features': study.features.order_by('name').all(),
        'questions': study.questions.all(),
        'num_images': study.tasks.values('image').distinct().count(),
        'num_annotators': study.tasks.values('annotator').distinct().count(),
        'num_tasks': study.tasks.count(),
        'responses': responses_page,
        'num_responses': responses.count(),
    }

    return render(request, 'studies/study_detail.html', context)


class CreateStudyView(CreateView):
    model = Study
    fields = ['name', 'description', 'features', 'questions']
    template_name = 'studies/study_create.html'

    def get_success_url(self):
        return reverse('study-detail', args=[self.object.id])

    def form_valid(self, form):
        form.instance.creator = self.request.user
        return super().form_valid(form)
