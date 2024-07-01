from django.db import IntegrityError
import pytest

from isic.core.models.isic_id import IsicId


@pytest.mark.django_db()
def test_isic_id_safe_create_success():
    IsicId.objects.create_random()

    assert IsicId.objects.count() == 1


# Since IntegrityError is expected, use a TransactionTestCase
@pytest.mark.django_db(transaction=True)
def test_isic_id_safe_create_retry(mocker):
    # Simulate a race condition where the first default returns a collision
    mocker.patch("isic.core.models.isic_id.secrets.randbelow", side_effect=[0, 1])

    IsicId.objects.create(id="ISIC_0000000")

    IsicId.objects.create_random()

    assert IsicId.objects.filter(id="ISIC_0000001").exists()


@pytest.mark.django_db(transaction=True)
def test_isic_id_safe_create_failure(mocker):
    # Simulate very unlikely race condition where every default returns a collision
    mocked_rand = mocker.patch("isic.core.models.isic_id.secrets.randbelow", return_value=0)
    IsicId.objects.create(id="ISIC_0000000")

    with pytest.raises(IntegrityError):
        IsicId.objects.create_random()

    assert mocked_rand.call_count == 10
