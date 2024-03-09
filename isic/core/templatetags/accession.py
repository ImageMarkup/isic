import json

from django import template
from django.core.serializers.json import DjangoJSONEncoder

register = template.Library()


@register.filter
def formatted(value):
    return json.dumps(value, indent=4, sort_keys=True, cls=DjangoJSONEncoder)
