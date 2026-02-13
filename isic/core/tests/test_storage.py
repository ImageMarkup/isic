from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.utils import timezone
from hypothesis import given
from hypothesis import strategies as st
import pytest

from isic.core.storages.s3 import CacheableCloudFrontStorage


@given(t_now=st.datetimes(timezones=st.just(None)))
def test_expiration_time(t_now):
    t_now = timezone.make_aware(t_now)
    t_next = CacheableCloudFrontStorage.next_expiration_time(t_now)
    expires_in = t_next - t_now
    assert expires_in > timedelta(days=6)
    assert expires_in <= timedelta(days=7)


def test_prevent_renaming():
    storages["default"].save("foo", ContentFile(b"test"))
    try:
        with pytest.raises(Exception, match="already exists."):
            storages["default"].save("foo", ContentFile(b"test"))
    finally:
        storages["default"].delete("foo")
