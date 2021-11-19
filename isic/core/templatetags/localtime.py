from datetime import datetime

from django import template

register = template.Library()


@register.inclusion_tag('core/partials/localtime.html')
def localtime(value: datetime):
    return {
        'dt': value,
    }
