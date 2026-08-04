from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse
from django.views.decorators.http import require_POST

from isic.engagement.forms import EmailDomainContributorForm
from isic.engagement.models import EmailDomainContributor
from isic.engagement.services.email_domain import (
    create_email_domain_contributor,
    update_email_domain_contributor,
)


@staff_member_required
def email_domain_list(request):
    form = EmailDomainContributorForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            create_email_domain_contributor(
                domain=form.cleaned_data["domain"], contributor=form.cleaned_data["contributor"]
            )
        except ValidationError as e:
            form.add_error(None, e)
        else:
            messages.success(request, "Email domain added successfully.")
            return HttpResponseRedirect(reverse("engagement/email-domain-list"))

    return render(
        request,
        "engagement/email_domain_list.html",
        {
            "form": form,
            "email_domains": EmailDomainContributor.objects.select_related("contributor"),
        },
    )


@staff_member_required
def email_domain_edit(request, pk):
    email_domain_contributor = get_object_or_404(EmailDomainContributor, pk=pk)
    form = EmailDomainContributorForm(request.POST or None, instance=email_domain_contributor)

    if request.method == "POST" and form.is_valid():
        try:
            update_email_domain_contributor(
                email_domain_contributor=email_domain_contributor,
                domain=form.cleaned_data["domain"],
                contributor=form.cleaned_data["contributor"],
            )
        except ValidationError as e:
            form.add_error(None, e)
        else:
            messages.success(request, "Email domain updated successfully.")
            return HttpResponseRedirect(reverse("engagement/email-domain-list"))

    return render(request, "engagement/email_domain_edit.html", {"form": form})


@staff_member_required
@require_POST
def email_domain_delete(request, pk):
    email_domain_contributor = get_object_or_404(EmailDomainContributor, pk=pk)

    email_domain_contributor.delete()

    messages.success(request, "Email domain deleted successfully.")
    return HttpResponseRedirect(reverse("engagement/email-domain-list"))
