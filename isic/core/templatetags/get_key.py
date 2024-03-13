from django import template

register = template.Library()


@register.filter()
def get_key(value, arg):
    if value and arg in value:
        return value[arg]

    return ""
