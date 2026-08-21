from django.urls import path

from isic.engagement.views.accession import (
    engagement_accession_list,
    engagement_accession_review,
)
from isic.engagement.views.email_domain import (
    email_domain_delete,
    email_domain_edit,
    email_domain_list,
)
from isic.engagement.views.user import engagement_user_assign, engagement_user_list

urlpatterns = [
    # Staff pages
    path(
        "staff/engagement/email-domains/",
        email_domain_list,
        name="engagement/email-domain-list",
    ),
    path(
        "staff/engagement/email-domains/<int:pk>/edit/",
        email_domain_edit,
        name="engagement/email-domain-edit",
    ),
    path(
        "staff/engagement/email-domains/<int:pk>/delete/",
        email_domain_delete,
        name="engagement/email-domain-delete",
    ),
    path(
        "staff/engagement/accessions/",
        engagement_accession_list,
        name="engagement/accession-list",
    ),
    path(
        "staff/engagement/accessions/review/",
        engagement_accession_review,
        name="engagement/accession-review",
    ),
    path("staff/engagement/users/", engagement_user_list, name="engagement/user-list"),
    path(
        "staff/engagement/users/<int:pk>/assign/",
        engagement_user_assign,
        name="engagement/user-assign",
    ),
]
