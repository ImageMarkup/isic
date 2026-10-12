from dataclasses import dataclass
from functools import cached_property
from itertools import groupby
from operator import attrgetter

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from isic.core.models import Collection, Doi, Image, Segmentation, SegmentationReview
from isic.core.models.collection import CollectionShare
from isic.core.models.doi import DraftDoi
from isic.core.models.image import ImageShare
from isic.core.permissions import needs_object_permission
from isic.ingest.models import (
    Accession,
    AccessionReview,
    BulkMetadataApplication,
    Cohort,
    Contributor,
    MetadataFile,
    MetadataVersion,
    PublishRequest,
    ZipUpload,
)
from isic.studies.models import Annotation, Study, StudyTask

USER_DETAIL_ROW_LIMIT = 100


@dataclass(frozen=True)
class UserDetailSection:
    key: str
    label: str
    group: str
    queryset: QuerySet

    @property
    def template_name(self) -> str:
        return f"core/user_detail/{self.key}.html"

    @cached_property
    def count(self) -> int:
        return self.queryset.count()


def _user_detail_sections(user: User) -> list[UserDetailSection]:
    return [
        UserDetailSection(
            "contributors",
            "Contributors",
            "Ingest",
            Contributor.objects.filter(Q(creator=user) | Q(owners=user))
            .distinct()
            .annotate(num_cohorts=Count("cohorts", distinct=True))
            .prefetch_related("owners")
            .order_by("-created"),
        ),
        UserDetailSection(
            "cohorts",
            "Cohorts",
            "Ingest",
            Cohort.objects.filter(creator=user)
            .select_related("contributor", "collection")
            .order_by("-created"),
        ),
        UserDetailSection(
            "zip_uploads",
            "Zip uploads",
            "Ingest",
            ZipUpload.objects.filter(creator=user).select_related("cohort").order_by("-created"),
        ),
        UserDetailSection(
            "accessions",
            "Accessions",
            "Ingest",
            Accession.objects.filter(creator=user)
            .select_related("cohort", "zip_upload", "image", "review", "engagement")
            .order_by("-created"),
        ),
        UserDetailSection(
            "metadata_files",
            "Metadata files",
            "Ingest",
            MetadataFile.objects.filter(creator=user).select_related("cohort").order_by("-created"),
        ),
        UserDetailSection(
            "metadata_applications",
            "Metadata applications",
            "Ingest",
            BulkMetadataApplication.objects.filter(creator=user)
            .select_related("metadata_file__cohort")
            .order_by("-created"),
        ),
        UserDetailSection(
            "metadata_versions",
            "Metadata versions",
            "Ingest",
            MetadataVersion.objects.filter(creator=user)
            .select_related("accession__cohort", "accession__image")
            .order_by("-created"),
        ),
        UserDetailSection(
            "accession_reviews",
            "Accession reviews",
            "Ingest",
            AccessionReview.objects.filter(creator=user)
            .select_related("accession__cohort", "accession__image")
            .order_by("-reviewed_at"),
        ),
        UserDetailSection(
            "publish_requests",
            "Publish requests",
            "Ingest",
            PublishRequest.objects.filter(creator=user)
            .annotate(num_accessions=Count("accessions"))
            .prefetch_related("collections")
            .order_by("-created"),
        ),
        UserDetailSection(
            "published_images",
            "Published images",
            "Archive",
            Image.objects.filter(creator=user)
            .select_related("accession__cohort")
            .order_by("-created"),
        ),
        UserDetailSection(
            "collections",
            "Collections",
            "Archive",
            Collection.objects.filter(creator=user)
            .select_related("doi", "cohort")
            .order_by("-created"),
        ),
        UserDetailSection(
            "collection_shares",
            "Collection shares",
            "Archive",
            CollectionShare.objects.filter(Q(grantor=user) | Q(grantee=user))
            .select_related("collection", "grantor", "grantee")
            .order_by("-created"),
        ),
        UserDetailSection(
            "image_shares",
            "Image shares",
            "Archive",
            ImageShare.objects.filter(Q(grantor=user) | Q(grantee=user))
            .select_related("image", "grantor", "grantee")
            .order_by("-created"),
        ),
        UserDetailSection(
            "dois",
            "DOIs",
            "Archive",
            Doi.objects.filter(creator=user).select_related("collection").order_by("-created"),
        ),
        UserDetailSection(
            "draft_dois",
            "Draft DOIs",
            "Archive",
            DraftDoi.objects.filter(creator=user).select_related("collection").order_by("-created"),
        ),
        UserDetailSection(
            "segmentations",
            "Segmentations",
            "Archive",
            Segmentation.objects.filter(creator=user)
            .select_related("image")
            .annotate(num_reviews=Count("reviews"))
            .order_by("-created"),
        ),
        UserDetailSection(
            "segmentation_reviews",
            "Segmentation reviews",
            "Archive",
            SegmentationReview.objects.filter(creator=user)
            .select_related("segmentation__image")
            .order_by("-created"),
        ),
        UserDetailSection(
            "studies",
            "Studies",
            "Studies",
            Study.objects.filter(Q(creator=user) | Q(owners=user))
            .distinct()
            .select_related("collection")
            .prefetch_related("owners")
            .order_by("-created"),
        ),
        UserDetailSection(
            "study_tasks",
            "Study tasks",
            "Studies",
            StudyTask.objects.filter(annotator=user)
            .select_related("study", "image", "annotation")
            .order_by("-created"),
        ),
        UserDetailSection(
            "annotations",
            "Annotations",
            "Studies",
            Annotation.objects.filter(annotator=user)
            .select_related("study", "image")
            .order_by("-created"),
        ),
    ]


@needs_object_permission("auth.view_staff")
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by("date_joined")
    return render(request, "core/staff_list.html", {"users": users, "total_users": User.objects})


@staff_member_required
def user_detail(request, pk):
    user = get_object_or_404(
        User.objects.select_related(
            "profile",
            "engagement_profile__default_contributor",
            "engagement_profile__default_cohort",
        ).prefetch_related("socialaccount_set"),
        pk=pk,
    )

    sections = _user_detail_sections(user)
    sections_by_key = {section.key: section for section in sections}

    if "section" in request.GET:
        if request.GET["section"] not in sections_by_key:
            raise Http404
        section = sections_by_key[request.GET["section"]]
    else:
        section = next((section for section in sections if section.count), None)

    visible_sections = [entry for entry in sections if entry.count or entry is section]

    rows = []
    if section:
        rows = list(section.queryset[:USER_DETAIL_ROW_LIMIT])

    return render(
        request,
        "core/user_detail.html",
        {
            "user": user,
            "email_addresses": user.emailaddress_set.order_by("-primary", "-verified", "email"),  # type: ignore[attr-defined]
            "section_groups": [
                (group, list(grouped))
                for group, grouped in groupby(visible_sections, attrgetter("group"))
            ],
            "section": section,
            "rows": rows,
        },
    )
