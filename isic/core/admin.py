from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models
from django.db.models import Count
from django.utils.safestring import mark_safe
from django_json_widget.widgets import JSONEditorWidget

from isic.core.models import (
    Collection,
    Doi,
    DuplicateImage,
    GirderDataset,
    GirderImage,
    Image,
    ImageAlias,
)

# general admin settings
# https://docs.djangoproject.com/en/3.1/ref/contrib/admin/#adminsite-objects
admin.site.site_header = 'ISIC Admin'
admin.site.site_title = 'ISIC Admin'
admin.site.index_title = ''

# TODO: unregister unnecessary apps from admin site


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


@admin.register(DuplicateImage)
class DuplicateImageAdmin(admin.ModelAdmin):
    list_select_related = ['accession', 'accession__distinctnessmeasure']
    list_display = ['id', 'isic_id', 'girder_id', 'accession', 'accession_distinctnessmeasure']
    search_fields = ['isic_id', 'girder_id']

    autocomplete_fields = ['accession']
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    @admin.display(ordering='accession__distinctnessmeasure')
    def accession_distinctnessmeasure(self, obj):
        return obj.accession.distinctnessmeasure


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
    search_fields = ['isic_id']

    autocomplete_fields = ['image']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_select_related = ['doi']
    list_display = ['name', 'num_images', 'doi']

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
