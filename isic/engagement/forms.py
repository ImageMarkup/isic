from django import forms

from isic.engagement.models import (
    EMAIL_DOMAIN_ERROR,
    EMAIL_DOMAIN_PATTERN,
    EmailDomainContributor,
)


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
