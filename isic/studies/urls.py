from django.urls import path

from isic.studies.views import (
    annotation_detail,
    study_detail,
    study_list,
    study_responses_csv,
    study_task_detail,
    view_mask,
)

urlpatterns = [
    path('studies/', study_list, name='study-list'),
    path('studies/<int:pk>/', study_detail, name='study-detail'),
    path('studies/tasks/<int:pk>/', study_task_detail, name='study-task-detail'),
    path(
        'studies/<int:pk>/download-responses/', study_responses_csv, name='study-download-responses'
    ),
    path('staff/masks/<int:markup_id>/', view_mask, name='view-mask'),
    path('staff/annotations/<int:pk>/', annotation_detail, name='annotation-detail'),
]
