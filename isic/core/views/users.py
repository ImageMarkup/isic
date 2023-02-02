from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render

from isic.core.models import Collection
from isic.core.models.segmentation import Segmentation, SegmentationReview
from isic.core.permissions import needs_object_permission
from isic.ingest.models import AccessionReview, Contributor
from isic.ingest.models.accession import Accession
from isic.ingest.models.metadata_file import MetadataFile
from isic.ingest.models.zip_upload import ZipUpload
from isic.studies.models import Annotation, Study, StudyTask


@needs_object_permission("auth.view_staff")
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by("email")
    return render(request, "core/staff_list.html", {"users": users, "total_users": User.objects})


@staff_member_required
def user_detail(request, pk):
    user = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    ctx = {
        "user": user,
        "email_addresses": user.emailaddress_set.order_by("-primary", "-verified", "email"),
    }

    ctx["sections"] = {
        "collections": Collection.objects.filter(creator=user).order_by("-created"),
        "contributors": Contributor.objects.select_related("creator")
        .prefetch_related("owners")
        .filter(owners=user)
        .order_by("-created"),
        "zip_uploads": ZipUpload.objects.select_related("cohort", "creator")
        .filter(creator=user)
        .order_by("-created"),
        "single_shot_accessions": Accession.objects.select_related("cohort", "creator")
        .filter(zip_upload=None, creator=user)
        .order_by("-created"),
        "accession_reviews": AccessionReview.objects.select_related("creator")
        .filter(creator=user)
        .order_by("-reviewed_at"),
        "metadata_files": MetadataFile.objects.select_related("cohort", "creator")
        .filter(creator=user)
        .order_by("-created"),
        "studies": Study.objects.select_related("creator", "collection")
        .filter(creator=user)
        .order_by("-created"),
        "study_tasks": StudyTask.objects.select_related("annotator", "image")
        .filter(annotator=user)
        .order_by("-created"),
        "annotations": Annotation.objects.select_related("study", "annotator", "image")
        .filter(annotator=user)
        .order_by("-created"),
        "segmentations": Segmentation.objects.select_related("creator", "image")
        .filter(creator=user)
        .order_by("-created"),
        "segmentation_reviews": SegmentationReview.objects.select_related("creator", "segmentation")
        .filter(creator=user)
        .order_by("-created"),
    }

    return render(request, "core/user_detail.html", ctx)
