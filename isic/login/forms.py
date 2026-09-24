from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from resonant_utils.allauth import FullNameSignupForm


class CaptchaSignupForm(FullNameSignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    field_order = [*FullNameSignupForm.field_order, "captcha"]


class AcceptTermsForm(forms.Form):
    accept_terms = forms.BooleanField(
        error_messages={"required": "You must agree to the Terms of Use to continue."}
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accept_terms"].label = format_html(
            'I agree to the <a href="{}" target="_blank" class="link">Terms of Use</a>',
            reverse("core/terms-of-use"),
        )
