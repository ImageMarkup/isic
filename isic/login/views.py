from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme

from isic.login.forms import AcceptTermsForm
from isic.login.services import accept_terms


@login_required
def accept_terms_of_use(request):
    form = AcceptTermsForm(request.POST or None)
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = settings.LOGIN_REDIRECT_URL

    if request.method == "POST" and form.is_valid():
        accept_terms(user=request.user)
        return HttpResponseRedirect(next_url)

    return render(request, "login/accept_terms.html", {"form": form, "next": next_url})
