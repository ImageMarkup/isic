from django.conf import settings


def js_sentry(request):
    return {"JS_SENTRY": settings.ISIC_JS_SENTRY}


def citation_styles(request):
    return {"CITATION_STYLES": settings.ISIC_DATACITE_CITATION_STYLES}
