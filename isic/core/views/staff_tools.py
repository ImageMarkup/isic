from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from isic.types import AuthenticatedHttpRequest


@staff_member_required
def staff_tools(request: AuthenticatedHttpRequest) -> HttpResponse:
    return render(request, "core/staff_tools.html")
