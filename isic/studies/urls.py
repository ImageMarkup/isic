from django.urls import path

from isic.studies.views.annotation import annotation_detail, view_mask
from isic.studies.views.study import (
    study_add_annotators,
    study_create,
    study_detail,
    study_edit,
    study_list,
    study_responses_csv,
)
from isic.studies.views.study_task import study_task_detail, study_task_detail_preview

urlpatterns = [
    path("studies/", study_list, name="studies/study-list"),
    path("studies/create/", study_create, name="studies/study-create"),
    path("studies/edit/<int:pk>/", study_edit, name="studies/study-edit"),
    path(
        "studies/<int:pk>/add-annotators/",
        study_add_annotators,
        name="studies/study-add-annotators",
    ),
    path("studies/<int:pk>/", study_detail, name="studies/study-detail"),
    path(
        "studies/tasks/<int:pk>/",
        study_task_detail,
        name="studies/study-task-detail",
    ),
    path(
        "studies/task-preview/<int:pk>/",
        study_task_detail_preview,
        name="studies/study-task-detail-preview",
    ),
    path(
        "studies/<int:pk>/download-responses/",
        study_responses_csv,
        name="studies/study-download-responses",
    ),
    path("staff/masks/<int:markup_id>/", view_mask, name="studies/view-mask"),
    path("staff/annotations/<int:pk>/", annotation_detail, name="studies/annotation-detail"),
]
