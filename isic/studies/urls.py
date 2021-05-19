from django.urls import path

from isic.studies.views import annotation_detail, study_create, study_detail, study_list, view_mask

urlpatterns = [
    path('staff/studies/create/', study_create, name='study-create'),
    path('staff/studies/', study_list, name='study-list'),
    path('staff/studies/<pk>/', study_detail, name='study-detail'),
    path('staff/masks/<markup_id>/', view_mask, name='view-mask'),
    path('staff/annotations/<pk>/', annotation_detail, name='annotation-detail'),
]