from django.urls import path

from isic.studies.views import (
    annotation_detail,
    study_create,
    study_detail,
    study_edit,
    study_list,
    study_responses_csv,
    study_task_detail,
    study_task_detail_preview,
    view_mask,
)

urlpatterns = [
    path("studies/", study_list, name="study-list"),
    path("studies/create/", study_create, name="study-create"),
    path("studies/edit/<int:pk>/", study_edit, name="study-edit"),
    path("studies/<int:pk>/", study_detail, name="study-detail"),
    path("studies/tasks/<int:pk>/", study_task_detail, name="study-task-detail"),
    path(
        "studies/task-preview/<int:pk>/",
        study_task_detail_preview,
        name="study-task-detail-preview",
    ),
    path(
        "studies/<int:pk>/download-responses/", study_responses_csv, name="study-download-responses"
    ),
    path("staff/masks/<int:markup_id>/", view_mask, name="view-mask"),
    path("staff/annotations/<int:pk>/", annotation_detail, name="annotation-detail"),
]
