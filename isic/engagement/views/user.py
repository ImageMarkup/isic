from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.engagement.forms import AssignExistingDefaultsForm, CondensedContributorCohortForm
from isic.engagement.models import EngagementProfile
from isic.engagement.services.email_domain import (
    suggest_cohort_for_contributor,
    suggest_contributor_for_users,
)
from isic.engagement.services.profile import assign_engagement_defaults
from isic.ingest.services.cohort import create_cohort
from isic.ingest.services.contributor import create_contributor


@staff_member_required
def engagement_user_list(request):
    only_unassigned = request.GET.get("only_unassigned", "1") == "1"

    profiles = EngagementProfile.objects.select_related(
        "user", "default_contributor", "default_cohort"
    ).order_by("-created")

    if only_unassigned:
        # a user isn't fully provisioned until they have both, and a contributor without a cohort
        # is a common half finished state since the cohort can be left for later.
        profiles = profiles.filter(
            Q(default_contributor__isnull=True) | Q(default_cohort__isnull=True)
        )

    paginator = Paginator(profiles, 50)
    page = paginator.get_page(request.GET.get("page"))

    suggestions = suggest_contributor_for_users([profile.user for profile in page])
    rows = [(profile, suggestions.get(profile.user_id)) for profile in page]

    return render(
        request,
        "engagement/user_list.html",
        {"page": page, "rows": rows, "only_unassigned": only_unassigned},
    )


def _assign_existing(request, engagement_profile: EngagementProfile) -> AssignExistingDefaultsForm:
    form = AssignExistingDefaultsForm(request.POST)

    if form.is_valid():
        try:
            assign_engagement_defaults(
                engagement_profile=engagement_profile,
                contributor=form.cleaned_data["contributor"],
                cohort=form.cleaned_data["cohort"],
            )
        except ValidationError as e:
            # the messages come from models whose field names don't line up with this form's,
            # so they're surfaced as non-field errors rather than reattached to fields.
            form.add_error(None, e.messages)

    return form


def _assign_created(
    request, engagement_profile: EngagementProfile
) -> CondensedContributorCohortForm:
    form = CondensedContributorCohortForm(request.POST)

    if form.is_valid():
        license_ = form.cleaned_data["cohort_default_copyright_license"]
        try:
            with transaction.atomic():
                # the engagement user is the creator rather than the staff member doing the
                # provisioning, since the contributor is being stood up on their behalf and
                # they're the one who has to own it to upload into it.
                contributor = create_contributor(
                    creator=engagement_profile.user,
                    institution_name=form.cleaned_data["institution_name"],
                    legal_contact_info=form.cleaned_data["legal_contact_info"],
                    default_attribution=form.cleaned_data["default_attribution"],
                    default_copyright_license=license_,
                )
                cohort = create_cohort(
                    creator=engagement_profile.user,
                    contributor=contributor,
                    name=form.cleaned_data["cohort_name"],
                    description=form.cleaned_data["cohort_description"],
                    default_copyright_license=license_,
                    # attribution is only asked for once, at the institution level, since the
                    # cohort being created is that institution's first.
                    default_attribution=contributor.default_attribution,
                )
                assign_engagement_defaults(
                    engagement_profile=engagement_profile,
                    contributor=contributor,
                    cohort=cohort,
                )
        except ValidationError as e:
            # the messages come from models whose field names don't line up with this form's,
            # so they're surfaced as non-field errors rather than reattached to fields.
            form.add_error(None, e.messages)

    return form


@staff_member_required
def engagement_user_assign(request, pk):
    engagement_profile = get_object_or_404(
        EngagementProfile.objects.select_related("user", "default_contributor", "default_cohort"),
        pk=pk,
    )
    suggested_contributor = suggest_contributor_for_users([engagement_profile.user]).get(
        engagement_profile.user_id
    )
    suggested_cohort = (
        suggest_cohort_for_contributor(suggested_contributor) if suggested_contributor else None
    )

    # which tab was submitted, and therefore which tab to reopen if it fails validation
    mode = "create_new" if request.POST.get("action") == "create_new" else "select_existing"
    initial_contributor = engagement_profile.default_contributor or suggested_contributor
    existing_form = AssignExistingDefaultsForm(
        initial={
            "contributor": initial_contributor,
            "cohort": engagement_profile.default_cohort or suggested_cohort,
        }
    )
    create_form = CondensedContributorCohortForm()

    if request.method == "POST":
        if mode == "create_new":
            create_form = _assign_created(request, engagement_profile)
            succeeded = create_form.is_valid()
        else:
            existing_form = _assign_existing(request, engagement_profile)
            succeeded = existing_form.is_valid()

        if succeeded:
            messages.success(request, f"Assigned defaults for {engagement_profile.user.email}.")
            return HttpResponseRedirect(reverse("engagement/user-list"))

    _, _, email_domain = engagement_profile.user.email.rpartition("@")

    # the cohort select is narrowed to one contributor's cohorts. seeding the options for the
    # contributor the page opens with means the initial selection is present on first paint,
    # rather than appearing only once the contributor autocomplete's fetch resolves.
    contributor_for_cohorts = (
        existing_form.cleaned_data.get("contributor")
        if existing_form.is_bound
        else initial_contributor
    )

    return render(
        request,
        "engagement/user_assign.html",
        {
            "engagement_profile": engagement_profile,
            "email_domain": email_domain,
            "existing_form": existing_form,
            "create_form": create_form,
            "mode": mode,
            "suggested_contributor": suggested_contributor,
            "suggested_cohort": suggested_cohort,
            "initial_cohorts": (
                list(contributor_for_cohorts.cohorts.order_by("name").values("id", "name"))
                if contributor_for_cohorts
                else []
            ),
        },
    )
