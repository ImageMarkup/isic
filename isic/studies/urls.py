from django.urls import path

from isic.studies.views import (
    annotation_detail,
    study_detail,
    study_list,
    study_task_detail,
    view_mask,
)

urlpatterns = [
    path('studies/', study_list, name='study-list'),
    path('studies/<pk>/', study_detail, name='study-detail'),
    path('studies/tasks/<pk>/', study_task_detail, name='study-task-detail'),
    path('staff/masks/<markup_id>/', view_mask, name='view-mask'),
    path('staff/annotations/<pk>/', annotation_detail, name='annotation-detail'),
]
