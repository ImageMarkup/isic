from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_staff_tools_permissions(staff_client, authenticated_client, client):
    assert staff_client.get(reverse("core/staff-tools")).status_code == 200
    assert authenticated_client.get(reverse("core/staff-tools")).status_code == 302
    assert client.get(reverse("core/staff-tools")).status_code == 302
