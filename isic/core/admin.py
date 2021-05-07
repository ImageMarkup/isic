from django.contrib import admin

from isic.core.models import DuplicateImage

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

    @admin.display(ordering='accession__distinctnessmeasure')
    def accession_distinctnessmeasure(self, obj):
        return obj.accession.distinctnessmeasure
