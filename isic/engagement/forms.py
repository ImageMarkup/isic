from django import forms

from isic.core.models.base import CopyrightLicense
from isic.engagement.models import (
    EMAIL_DOMAIN_ERROR,
    EMAIL_DOMAIN_PATTERN,
    EmailDomainContributor,
)
from isic.ingest.models import Cohort, Contributor


class EmailDomainContributorForm(forms.ModelForm):
    class Meta:
        model = EmailDomainContributor
        fields = ["domain", "contributor"]
        widgets = {
            "domain": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    # an HTML5 pattern can't be made case insensitive, so this accepts either
                    # case rather than rejecting a mixed case domain in the browser.
                    "pattern": EMAIL_DOMAIN_PATTERN,
                    "title": EMAIL_DOMAIN_ERROR,
                }
            ),
            "contributor": forms.HiddenInput(),
        }
        help_texts = {
            "contributor": "The contributor users with this email domain belong to.",
        }


class AssignExistingDefaultsForm(forms.Form):
    """Pick an existing contributor, and optionally one of its cohorts, as a user's defaults."""

    contributor = forms.ModelChoiceField(
        widget=forms.HiddenInput(),
        queryset=Contributor.objects.all(),
        required=True,
        label="Contributor",
        help_text="Uploads from this user will be attributed to this contributor.",
    )
    # rendered by hand as a <select> narrowed to the chosen contributor's cohorts, so the widget
    # here is only a safeguard: a stray {{ form.cohort }} emits a hidden input rather than an
    # <option> for every cohort in the archive. the queryset is still what validates the post.
    cohort = forms.ModelChoiceField(
        widget=forms.HiddenInput(),
        queryset=Cohort.objects.all(),
        # a contributor without a cohort is a valid half provisioned state, so the cohort can be
        # left for later. the reverse isn't allowed, see EngagementProfile's check constraint.
        required=False,
        label="Cohort",
        help_text="The cohort carries the license applied to every image submitted under it.",
    )

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = cleaned_data if cleaned_data is not None else {}
        contributor = cleaned_data.get("contributor")
        cohort = cleaned_data.get("cohort")

        if contributor and cohort and cohort.contributor_id != contributor.pk:
            raise forms.ValidationError(
                f"{cohort.name} belongs to {cohort.contributor.institution_name}, "
                f"not {contributor.institution_name}."
            )

        return cleaned_data


class CondensedContributorCohortForm(forms.Form):
    """
    Create a contributor and its first cohort in one step, to assign as a user's defaults.

    A condensed version of the full contributor and cohort create forms: it asks only for the
    fields that can't be defaulted, since staff are filling it out on someone else's behalf.
    """

    # the fields that end up visible outside the Archive, badged as such in the template. the
    # rest of the wording is deliberately terser than the model help text, which is written for
    # contributors filling out the full upload forms rather than staff provisioning someone.
    public_fields = ("default_attribution", "cohort_default_copyright_license")

    institution_name = forms.CharField(
        max_length=255,
        label="Institution Name",
        help_text="The full name of the affiliated institution. Private.",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered input-sm w-full",
                "placeholder": "e.g. Memorial Sloan Kettering Cancer Center",
            }
        ),
    )
    legal_contact_info = forms.CharField(
        label="Legal Contact Information",
        help_text="The person or institution responsible for legal inquiries about the data. "
        "Private.",
        widget=forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered textarea-sm w-full",
                "rows": 3,
                "placeholder": "Name, title, email, and mailing address of the person or office "
                "responsible for legal inquiries",
            }
        ),
    )
    # required here even though the model allows it to be blank, because it's copied down to the
    # cohort, where Cohort.default_attribution has no blank=True.
    default_attribution = forms.CharField(
        max_length=200,
        label="Default Attribution",
        help_text="Text that users of these images must reproduce to comply with Creative "
        "Commons Attribution requirements.",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered input-sm w-full",
                "placeholder": "e.g. Memorial Sloan Kettering Cancer Center",
            }
        ),
    )

    cohort_name = forms.CharField(
        max_length=255,
        label="Cohort Name",
        help_text="A short name for this group of images. Private.",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered input-sm w-full",
                "placeholder": "e.g. MSK Dermoscopy 2024",
            }
        ),
    )
    cohort_description = forms.CharField(
        label="Cohort Description",
        help_text="Private. Markdown supported.",
        widget=forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered textarea-sm w-full",
                "rows": 3,
                "placeholder": "Describe the dataset: imaging modality, patient population, "
                "collection period, etc.",
            }
        ),
    )
    cohort_default_copyright_license = forms.ChoiceField(
        choices=[
            ("", "Select a license..."),
            *(
                (
                    value,
                    f"{label} (Not recommended)" if value == CopyrightLicense.CC_BY_NC else label,
                )
                for value, label in CopyrightLicense.choices
            ),
        ],
        label="Default Copyright License",
        widget=forms.Select(attrs={"class": "select select-bordered select-sm w-full"}),
    )
