from django.conf import settings


def noindex(request):
    return {'NOINDEX': settings.ISIC_NOINDEX}
