from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from isic.engagement.models import EngagementProfile


@staff_member_required
def engagement_user_list(request):
    profiles = EngagementProfile.objects.select_related(
        "user", "default_contributor", "default_cohort"
    ).order_by("-created")

    return render(request, "engagement/user_list.html", {"profiles": profiles})
