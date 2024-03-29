from django.conf import settings


def noindex(request):
    return {"NOINDEX": settings.ISIC_NOINDEX}


def sandbox_banner(request):
    return {"SANDBOX_BANNER": settings.ISIC_SANDBOX_BANNER}


def placeholder_images(request):
    return {"PLACEHOLDER_IMAGES": settings.ISIC_PLACEHOLDER_IMAGES}
