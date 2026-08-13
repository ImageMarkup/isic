from django.contrib.auth.models import User
from django.urls import reverse
from django_recaptcha.client import RecaptchaResponse
from django_recaptcha.constants import TEST_PUBLIC_KEY
from faker import Faker
import pytest

fake = Faker()


@pytest.mark.django_db
def test_signup_requires_captcha(client, settings, mocker):
    password = fake.password(length=20)
    email = fake.email()
    form_data = {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": email,
        "password1": password,
        "password2": password,
        "g-recaptcha-response": fake.pystr(),
    }
    signup_url = reverse("account_signup")

    challenge = client.get(signup_url)

    assert challenge.status_code == 200
    assert 'class="g-recaptcha' in challenge.content.decode()
    assert TEST_PUBLIC_KEY in challenge.content.decode()

    submit = mocker.patch("django_recaptcha.fields.client.submit")
    submit.return_value = RecaptchaResponse(is_valid=False, error_codes=["invalid-input-response"])

    rejected = client.post(signup_url, form_data)

    assert rejected.status_code == 200
    assert "Error verifying reCAPTCHA" in rejected.content.decode()
    assert not User.objects.filter(email=email).exists()

    submit.return_value = RecaptchaResponse(is_valid=True)

    accepted = client.post(signup_url, form_data)

    assert accepted.status_code == 302
    assert User.objects.filter(email=email).exists()
