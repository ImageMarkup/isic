from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models
from django.db.models import Count
from django.utils.safestring import mark_safe
from django_json_widget.widgets import JSONEditorWidget

from isic.core.models import Collection, DuplicateImage, Image, ImageRedirect

# general admin settings
# https://docs.djangoproject.com/en/3.1/ref/contrib/admin/#adminsite-objects
admin.site.site_header = 'ISIC Admin'
admin.site.site_title = 'ISIC Admin'
admin.site.index_title = ''

# TODO: unregister unnecessary apps from admin site


@admin.register(DuplicateImage)
class DuplicateImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'isic_id', 'girder_id', 'accession', 'accession_distinctnessmeasure']
    list_select_related = ['accession', 'accession__distinctnessmeasure']
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
    autocomplete_fields = ['accession']
    search_fields = ['isic_id']
    list_display = ['isic_id', 'created', 'public']
    list_filter = ['public']
    readonly_fields = ['created', 'modified', 'thumbnail']

    @admin.display()
    def thumbnail(self, obj):
        return mark_safe(f'<img src="{obj.accession.blob.url}" width="300" height="300" />')


@admin.register(ImageRedirect)
class ImageRedirectAdmin(admin.ModelAdmin):
    autocomplete_fields = ['image']
    search_fields = ['isic_id']
    list_display = ['isic_id', 'image']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    exclude = ['images']
    list_display = ['name', 'num_images']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            num_images=Count('images', distinct=True),
        )
        return qs

    @admin.display()
    def num_images(self, obj):
        return intcomma(obj.num_images)
