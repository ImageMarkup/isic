from datetime import datetime

from django.conf import settings
from jinja2 import Environment
from markupsafe import Markup


def localtime_filter(dt: datetime):
    return Markup(f"""
<local-time datetime="{dt.isoformat()}"
            month="short"
            day="numeric"
            year="numeric"
            hour="numeric"
            minute="numeric"></local-time>
""")


def querystring_filter(request, **kwargs):
    query = request.GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return "?" + query.urlencode() if query else ""


def environment(**options):
    env = Environment(**options)  # noqa: S701 django overrides this and sets autoescape=True

    env.globals.update(
        {
            "debug": settings.DEBUG,
            # ISIC-specific "context processors"
            "NOINDEX": settings.ISIC_NOINDEX,
            "SANDBOX_BANNER": settings.ISIC_SANDBOX_BANNER,
            "PLACEHOLDER_IMAGES": settings.ISIC_PLACEHOLDER_IMAGES,
        }
    )
    return env
