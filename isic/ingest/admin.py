from datetime import UTC, datetime
import logging

from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Count
from django.http import HttpResponse
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html
from resonant_utils.admin import ReadonlyTabularInline

from isic.core.admin import StaffReadonlyAdmin
from isic.core.utils.csv import EscapingDictWriter
from isic.ingest.models import (
    Accession,
    AccessionReview,
    BulkMetadataApplication,
    Cohort,
    Contributor,
    Lesion,
    MetadataFile,
    Patient,
    ZipUpload,
)
from isic.ingest.models.metadata_version import MetadataVersion
from isic.ingest.models.publish_request import PublishRequest
from isic.ingest.models.rcm_case import RcmCase
from isic.ingest.tasks import extract_zip_task

logger = logging.getLogger(__name__)


class CohortInline(ReadonlyTabularInline):
    model = Cohort
    fields = ["id", "name", "created", "creator", "description"]


class AccessionInline(ReadonlyTabularInline):
    model = Accession


class MetadataVersionInline(ReadonlyTabularInline):
    model = MetadataVersion


class AccessionReviewInline(ReadonlyTabularInline):
    model = AccessionReview
    fields = ["reviewed_at", "creator", "value"]
    ordering = ["-reviewed_at"]


class MetadataFileInline(ReadonlyTabularInline):
    model = MetadataFile


class ZipInline(ReadonlyTabularInline):
    model = ZipUpload


@admin.register(Contributor)
class ContributorAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator"]
    list_display = ["institution_name", "created", "creator", "cohorts", "accessions"]
    search_fields = ["institution_name", "creator__username"]

    autocomplete_fields = ["creator", "owners"]
    readonly_fields = ["created", "modified"]
    inlines = [CohortInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            cohorts_count=Count("cohorts", distinct=True),
            accessions_count=Count("cohorts__accessions", distinct=True),
        )

    @admin.display(ordering="cohorts_count")
    def cohorts(self, obj):
        return intcomma(obj.cohorts_count)

    @admin.display(ordering="accessions_count")
    def accessions(self, obj):
        return intcomma(obj.accessions_count)


@admin.register(Cohort)
class CohortAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator", "contributor"]
    list_display = [
        "id",
        "name",
        "creator",
        "created",
        "zips",
        "metadata_files",
        "contributor",
    ]
    search_fields = ["name", "creator__username"]
    actions = [
        "export_file_mapping",
        "publish_cohort_publicly",
        "publish_cohort_privately",
    ]

    autocomplete_fields = ["creator", "contributor"]
    readonly_fields = ["created", "modified"]
    inlines = [ZipInline, MetadataFileInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            zip_uploads_count=Count("zip_uploads", distinct=True),
            metadata_files_count=Count("metadata_files", distinct=True),
        )

    @admin.display(ordering="zip_uploads_count")
    def zips(self, obj):
        return intcomma(obj.zip_uploads_count)

    @admin.display(ordering="metadata_files_count")
    def metadata_files(self, obj):
        return intcomma(obj.metadata_files_count)

    @admin.action(description="Export original file mapping")
    def export_file_mapping(self, request, queryset):
        current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="cohort_file_mapping_{current_time}.csv"'
        )

        writer = EscapingDictWriter(response, ["contributor", "cohort", "filename", "isic_id"])

        writer.writeheader()
        for cohort in queryset.select_related("contributor"):
            for accession in cohort.accessions.values(
                "original_blob_name",
                "image__isic_id",
            ).iterator():
                d = {
                    "contributor": cohort.contributor.institution_name,
                    "cohort": cohort.name,
                    "filename": accession["original_blob_name"],
                    "isic_id": accession["image__isic_id"],
                }
                writer.writerow(d)
        return response


@admin.register(MetadataFile)
class MetadataFileAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator", "cohort"]
    list_display = ["blob_name", "human_blob_size", "created", "creator", "cohort"]
    search_fields = ["blob_name", "creator__username"]

    autocomplete_fields = ["creator", "cohort"]
    readonly_fields = ["created", "modified", "blob_name", "human_blob_size"]

    @admin.display(description="Blob Size", ordering="blob_size")
    def human_blob_size(self, obj):
        return filesizeformat(obj.blob_size)


@admin.register(BulkMetadataApplication)
class BulkMetadataApplicationAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator", "metadata_file"]
    list_display = ["id", "created", "creator", "metadata_file", "message"]
    search_fields = ["id", "creator__username", "metadata_file__blob_name"]

    autocomplete_fields = ["creator", "metadata_file"]
    readonly_fields = ["created"]


class AccessionReviewedFilter(admin.SimpleListFilter):
    title = "reviewed"
    parameter_name = "reviewed"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.filter(review__isnull=False)
        if value == "no":
            return queryset.exclude(review__isnull=False)
        return queryset


@admin.register(Lesion)
class LesionAdmin(StaffReadonlyAdmin):
    list_display = ["cohort", "private_lesion_id", "id"]
    search_fields = ["id", "private_lesion_id"]


@admin.register(Patient)
class PatientAdmin(StaffReadonlyAdmin):
    list_display = ["cohort", "private_patient_id", "id"]
    search_fields = ["id", "private_patient_id"]


@admin.register(RcmCase)
class RcmCaseAdmin(StaffReadonlyAdmin):
    list_display = ["cohort", "private_rcm_case_id", "id"]
    search_fields = ["id", "private_rcm_case_id"]


@admin.register(Accession)
class AccessionAdmin(StaffReadonlyAdmin):
    list_select_related = ["cohort"]
    list_display = [
        "id",
        "original_blob_name",
        "human_original_blob_size",
        "created",
        "status",
        "cohort",
    ]
    autocomplete_fields = ["lesion", "patient"]
    list_filter = ["status", AccessionReviewedFilter]
    search_fields = ["cohort__name", "original_blob_name", "girder_id"]
    search_help_text = "Search by cohort name, original blob name, or Girder ID."

    readonly_fields = ["created", "modified", "thumbnail_image", "distinctnessmeasure"]
    inlines = [AccessionReviewInline, MetadataVersionInline]

    @admin.display(description="Original Blob Size", ordering="original_blob_size")
    def human_original_blob_size(self, obj):
        return filesizeformat(obj.original_blob_size)

    @admin.display()
    def thumbnail_image(self, obj):
        return format_html('<img src="{}" />', obj.thumbnail_256.url)


@admin.register(AccessionReview)
class AccessionReviewAdmin(StaffReadonlyAdmin):
    list_select_related = ["accession", "creator", "accession__cohort"]
    list_display = ["id", "accession__cohort", "accession", "creator", "reviewed_at", "value"]

    autocomplete_fields = ["accession", "creator"]


@admin.register(ZipUpload)
class ZipAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator", "cohort"]
    list_display = [
        "blob_name",
        "human_blob_size",
        "created",
        "creator",
        "status",
        "fail_reason",
        "cohort",
    ]
    list_filter = ["status"]
    search_fields = ["blob_name", "creator__username"]
    actions = ["extract_zip"]

    autocomplete_fields = ["creator", "cohort"]
    readonly_fields = ["created", "modified", "blob_name", "human_blob_size"]

    @admin.display(description="Blob Size", ordering="blob_size")
    def human_blob_size(self, obj):
        return filesizeformat(obj.blob_size)

    @admin.action(description="Extract zip")
    def extract_zip(self, request, queryset):
        for zip_file in queryset:
            zip_file.reset()
            extract_zip_task.delay_on_commit(zip_file.pk)


@admin.register(PublishRequest)
class PublishRequestAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator"]
    list_display = ["id", "created", "creator", "public", "accession_count"]
    list_filter = ["public", "created"]
    search_fields = ["id", "creator__username"]

    autocomplete_fields = ["creator", "collections"]
    readonly_fields = ["created"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(accessions_count=Count("accessions", distinct=True))

    @admin.display(ordering="accessions_count")
    def accession_count(self, obj):
        return intcomma(obj.accessions_count)
