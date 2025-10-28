from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Count
from django.utils.html import format_html
from resonant_utils.admin import ReadonlyTabularInline

from isic.core.models import Collection, Doi, GirderDataset, GirderImage, Image, ImageAlias
from isic.core.models.doi import DoiRelatedIdentifier, DraftDoi, DraftDoiRelatedIdentifier
from isic.core.models.segmentation import Segmentation, SegmentationReview
from isic.core.models.supplemental_file import DraftSupplementalFile, SupplementalFile

# general admin settings
# https://docs.djangoproject.com/en/3.1/ref/contrib/admin/#adminsite-objects
admin.site.site_header = "ISIC Admin"
admin.site.site_title = "ISIC Admin"
admin.site.index_title = ""


# TODO: unregister unnecessary apps from admin site


class StaffReadonlyAdmin(admin.ModelAdmin):
    """
    Give staff readonly access to the admin class.

    This only impacts django actions if they've been specified with the permissions
    flag (e.g. the core delete action).
    """

    def has_add_permission(self, request):
        check = super().has_add_permission(request)
        return check and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        check = super().has_delete_permission(request, obj=obj)
        return check and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        check = super().has_change_permission(request, obj=obj)
        return check and request.user.is_superuser


class HasMaskFilter(admin.SimpleListFilter):
    title = "mask"
    parameter_name = "mask"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.exclude(mask="")
        if value == "no":
            return queryset.filter(mask="")
        return queryset


class MagicCollectionFilter(admin.SimpleListFilter):
    title = "magic"
    parameter_name = "magic"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.exclude(cohort=None)
        if value == "no":
            return queryset.filter(cohort=None)
        return queryset


class SegmentationReviewInline(ReadonlyTabularInline):
    model = SegmentationReview
    fields = ["created", "creator", "skill", "approved"]


@admin.register(SegmentationReview)
class SegmentationReviewAdmin(StaffReadonlyAdmin):
    list_display = ["id", "created", "creator", "skill", "approved"]
    list_filter = ["approved", "skill"]

    search_fields = ["segmentation__girder_id"]
    autocomplete_fields = ["creator", "segmentation"]


@admin.register(Segmentation)
class SegmentationAdmin(StaffReadonlyAdmin):
    list_display = ["id", "created", "creator", "image", "num_reviews"]
    list_filter = [HasMaskFilter]
    inlines = [SegmentationReviewInline]

    readonly_fields = ["mask_thumbnail"]

    search_fields = ["id", "girder_id"]
    autocomplete_fields = ["creator", "image"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            num_reviews=Count("reviews", distinct=True),
        )

    @admin.display(ordering="num_reviews")
    def num_reviews(self, obj):
        return intcomma(obj.num_reviews)

    @admin.display()
    def mask_thumbnail(self, obj):
        if obj.mask:
            return format_html('<img src="{}" width="256" height="256" />', obj.mask.url)


@admin.register(GirderDataset)
class GirderDatasetAdmin(StaffReadonlyAdmin):
    list_display = ["id", "name", "public", "images"]
    search_fields = ["name"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            images_count=Count("images", distinct=True),
        )

    @admin.display(ordering="images_count")
    def images(self, obj):
        return intcomma(obj.images_count)


@admin.register(GirderImage)
class GirderImageAdmin(StaffReadonlyAdmin):
    list_select_related = ["isic", "dataset"]
    list_display = ["id", "isic", "item_id", "dataset", "original_blob_dm", "status", "pre_review"]
    list_filter = ["status", "pre_review"]
    search_fields = ["isic__id", "item_id"]

    readonly_fields = [
        "isic",
        "item_id",
        "file_id",
        "dataset",
        "original_filename",
        "original_file_relpath",
        "metadata",
        "unstructured_metadata",
        "original_blob_dm",
        "stripped_blob_dm",
        "accession",
    ]


@admin.register(Image)
class ImageAdmin(StaffReadonlyAdmin):
    # Using "isic_id" will not allow ordering
    list_display = ["isic", "created", "public"]
    list_filter = ["public"]
    # The related field ("isic_id") will not directly allow an icontains lookup
    search_fields = ["isic__id"]

    autocomplete_fields = ["accession"]
    readonly_fields = ["created", "modified", "thumbnail_image"]

    @admin.display()
    def thumbnail_image(self, obj):
        return format_html('<img src="{}" />', obj.accession.thumbnail_256.url)


@admin.register(ImageAlias)
class ImageAliasAdmin(StaffReadonlyAdmin):
    list_display = ["isic_id", "image"]
    search_fields = ["isic__id"]

    autocomplete_fields = ["image"]


@admin.register(Collection)
class CollectionAdmin(StaffReadonlyAdmin):
    list_select_related = ["creator", "doi"]
    list_filter = [
        "public",
        "pinned",
        MagicCollectionFilter,
        ("doi", admin.EmptyFieldListFilter),
        "locked",
    ]
    list_display = [
        "name",
        "created",
        "creator",
        "public",
        "pinned",
        "locked",
        "doi",
    ]
    search_fields = ["creator__email", "name", "doi__id"]
    search_help_text = "Search collections by name, or creator email."

    autocomplete_fields = ["creator"]

    exclude = ["images"]


class BaseDoiAdmin(StaffReadonlyAdmin):
    list_select_related = ["collection"]
    list_display = ["id", "external_url", "collection", "bundle", "num_supplemental_files"]
    autocomplete_fields = ["creator"]
    search_fields = ["id", "collection__name"]
    search_help_text = "Search DOIs by ID or collection name."

    @admin.display(ordering="num_supplemental_files", description="Number of supplemental files")
    def num_supplemental_files(self, obj):
        return intcomma(obj.num_supplemental_files)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            num_supplemental_files=Count("supplemental_files", distinct=True),
        )


class SupplementalFileInline(admin.TabularInline):
    model = SupplementalFile
    extra = 0


class RelatedIdentifierInline(admin.TabularInline):
    model = DoiRelatedIdentifier
    extra = 0


@admin.register(Doi)
class DoiAdmin(BaseDoiAdmin):
    inlines = [SupplementalFileInline, RelatedIdentifierInline]


class DraftSupplementalFileInline(admin.TabularInline):
    model = DraftSupplementalFile
    extra = 0


class DraftRelatedIdentifierInline(admin.TabularInline):
    model = DraftDoiRelatedIdentifier
    extra = 0


@admin.register(DraftDoi)
class DraftDoiAdmin(BaseDoiAdmin):
    inlines = [DraftSupplementalFileInline, DraftRelatedIdentifierInline]
    list_display = [
        "id",
        "external_url",
        "collection",
        "bundle",
        "num_supplemental_files",
        "is_publishing",
    ]
    readonly_fields = ["is_publishing"]
