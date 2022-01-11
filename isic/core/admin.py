from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Count
from django.utils.safestring import mark_safe
from girder_utils.admin import ReadonlyTabularInline

from isic.core.models import Collection, Doi, GirderDataset, GirderImage, Image, ImageAlias
from isic.core.models.segmentation import Segmentation, SegmentationReview

# general admin settings
# https://docs.djangoproject.com/en/3.1/ref/contrib/admin/#adminsite-objects
admin.site.site_header = 'ISIC Admin'
admin.site.site_title = 'ISIC Admin'
admin.site.index_title = ''


# TODO: unregister unnecessary apps from admin site


class HasMaskFilter(admin.SimpleListFilter):
    title = 'mask'
    parameter_name = 'mask'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.exclude(mask='')
        elif value == 'no':
            return queryset.filter(mask='')
        return queryset


class SegmentationReviewInline(ReadonlyTabularInline):
    model = SegmentationReview
    fields = ['created', 'creator', 'skill', 'approved']


@admin.register(SegmentationReview)
class SegmentationReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'creator', 'skill', 'approved']
    list_filter = ['approved', 'skill']

    search_fields = ['segmentation__girder_id']
    autocomplete_fields = ['creator', 'segmentation']


@admin.register(Segmentation)
class SegmentationAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'creator', 'image', 'num_reviews']
    list_filter = [HasMaskFilter]
    inlines = [SegmentationReviewInline]

    readonly_fields = ['mask_thumbnail']

    search_fields = ['id', 'girder_id']
    autocomplete_fields = ['creator', 'image']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            num_reviews=Count('reviews', distinct=True),
        )
        return qs

    @admin.display(ordering='num_reviews')
    def num_reviews(self, obj):
        return intcomma(obj.num_reviews)

    @admin.display()
    def mask_thumbnail(self, obj):
        if obj.mask:
            return mark_safe(f'<img src="{obj.mask.url}" width="256" height="256" />')


@admin.register(GirderDataset)
class GirderDatasetAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'public', 'images']
    search_fields = ['name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            images_count=Count('images', distinct=True),
        )
        return qs

    @admin.display(ordering='images_count')
    def images(self, obj):
        return intcomma(obj.images_count)


@admin.register(GirderImage)
class GirderImageAdmin(admin.ModelAdmin):
    list_select_related = ['isic', 'dataset']
    list_display = ['id', 'isic', 'item_id', 'dataset', 'original_blob_dm', 'status', 'pre_review']
    list_filter = ['status', 'pre_review']
    search_fields = ['isic__id', 'item_id']

    readonly_fields = [
        'isic',
        'item_id',
        'file_id',
        'dataset',
        'original_filename',
        'original_file_relpath',
        'metadata',
        'unstructured_metadata',
        'original_blob_dm',
        'stripped_blob_dm',
        'accession',
    ]


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    # Using "isic_id" will not allow ordering
    list_display = ['isic', 'created', 'public']
    list_filter = ['public']
    # The related field ("isic_id") will not directly allow an icontains lookup
    search_fields = ['isic__id']

    autocomplete_fields = ['accession']
    readonly_fields = ['created', 'modified', 'thumbnail_image']

    @admin.display()
    def thumbnail_image(self, obj):
        return mark_safe(f'<img src="{obj.accession.thumbnail_256.url}" />')


@admin.register(ImageAlias)
class ImageAliasAdmin(admin.ModelAdmin):
    list_display = ['isic_id', 'image']
    search_fields = ['isic__id']

    autocomplete_fields = ['image']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_select_related = ['creator', 'doi']
    list_filter = ['public', 'official']
    list_display = ['name', 'creator', 'num_images', 'public', 'official', 'doi']

    autocomplete_fields = ['creator']

    exclude = ['images']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            num_images=Count('images', distinct=True),
        )
        return qs

    @admin.display()
    def num_images(self, obj):
        return intcomma(obj.num_images)


@admin.register(Doi)
class DoiAdmin(admin.ModelAdmin):
    list_select_related = ['collection']
    list_display = ['id', 'url', 'collection']
