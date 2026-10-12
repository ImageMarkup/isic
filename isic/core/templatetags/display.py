from django import template
from django.contrib.auth.models import User

from isic.core.utils.display import user_nicename as user_nicename_util

register = template.Library()


@register.filter
def user_nicename(user: User):
    return user_nicename_util(user)


@register.inclusion_tag("core/partials/user_link.html", takes_context=True)
def user_link(context, user: User, label: str | None = None):
    # the user detail page is staff only, so everyone else just sees the label
    return {
        "linked_user": user,
        "label": label or str(user),
        "linkable": context["request"].user.is_staff,
    }
