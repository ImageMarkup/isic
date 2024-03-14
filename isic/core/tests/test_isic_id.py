from django.db import IntegrityError
import pytest

from isic.core.models.isic_id import IsicId


@pytest.mark.django_db()
def test_isic_id_safe_create_success():
    IsicId.safe_create()

    assert IsicId.objects.count() == 1


# Since IntegrityError is expected, use a TransactionTestCase
@pytest.mark.django_db(transaction=True)
def test_isic_id_safe_create_retry(mocker):
    # Simulate a race condition where the first default returns a collision
    id_field = IsicId._meta.get_field("id")
    # Since the "default" property is cached, mock "get_default"
    mocker.patch.object(id_field, "get_default", side_effect=["ISIC_0000000", "ISIC_0000001"])

    IsicId.objects.create(id="ISIC_0000000")

    IsicId.safe_create()

    assert IsicId.objects.filter(id="ISIC_0000001").exists()


@pytest.mark.django_db(transaction=True)
def test_isic_id_safe_create_failure(mocker):
    # Simulate very unlikely race condition where every default returns a collision
    id_field = IsicId._meta.get_field("id")
    mock_default = mocker.patch.object(id_field, "get_default", return_value="ISIC_0000000")

    IsicId.objects.create(id="ISIC_0000000")

    with pytest.raises(IntegrityError):
        IsicId.safe_create()

    assert mock_default.call_count == 10
