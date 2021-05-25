from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from isic.studies.models import Annotation, Markup, Study


@staff_member_required
def study_list(request):
    studies = Study.objects.all()
    return render(request, 'studies/study_list.html', {'studies': studies})


@staff_member_required
def view_mask(request, markup_id):
    markup = get_object_or_404(Markup.objects.values('mask'), pk=markup_id)
    return HttpResponse(markup['mask'], content_type='image/png')


@staff_member_required
def annotation_detail(request, pk):
    annotation = get_object_or_404(
        Annotation.objects.select_related('image', 'study', 'annotator')
        .prefetch_related('markups__feature')
        .prefetch_related('responses__choice')
        .prefetch_related('responses__question'),
        pk=pk,
    )
    return render(
        request,
        'studies/annotation_detail.html',
        {'annotation': annotation},
    )


@staff_member_required
def study_detail(request, pk):
    study = get_object_or_404(
        Study.objects.annotate(
            num_images=Count('tasks__image', distinct=True),
            num_annotators=Count('tasks__annotator', distinct=True),
            num_tasks=Count('tasks', distinct=True),
        )
        .prefetch_related('questions')
        .prefetch_related('features'),
        pk=pk,
    )
    annotations = (
        Annotation.objects.filter(study=study)
        .select_related('annotator', 'image')
        .order_by('created')
    )
    paginator = Paginator(annotations, 50)
    annotations_page = paginator.get_page(request.GET.get('page'))
    context = {
        'study': study,
        'annotations': annotations_page,
        'num_annotations': paginator.count,
    }

    return render(request, 'studies/study_detail.html', context)
