from django.conf import settings


def placeholder_images(request):
    return {"PLACEHOLDER_IMAGES": settings.ISIC_PLACEHOLDER_IMAGES}


def js_sentry(request):
    return {"JS_SENTRY": settings.ISIC_JS_SENTRY}


def js_browser_sync(request):
    return {"JS_BROWSER_SYNC": settings.ISIC_JS_BROWSER_SYNC}


def citation_styles(request):
    return {"CITATION_STYLES": settings.ISIC_DATACITE_CITATION_STYLES}
