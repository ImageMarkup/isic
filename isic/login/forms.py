from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from resonant_utils.allauth import FullNameSignupForm


class CaptchaSignupForm(FullNameSignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    field_order = [*FullNameSignupForm.field_order, "captcha"]
