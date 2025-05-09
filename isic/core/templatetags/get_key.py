from django import template

register = template.Library()


# replace with resonant_utils: https://github.com/kitware-resonant/django-resonant-utils/blob/master/resonant_utils/templatetags/resonant_utils.py ??
@register.filter()
def get_key(value, arg):
    if value and arg in value:
        return value[arg]

    return ""
