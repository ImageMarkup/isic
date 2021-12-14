from django import template
from django.contrib.auth.models import User

from isic.core.utils.display import user_nicename as user_nicename_util

register = template.Library()


@register.filter
def user_nicename(user: User):
    return user_nicename_util(user)
