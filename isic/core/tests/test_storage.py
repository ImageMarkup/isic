from datetime import timedelta

from django.utils import timezone
from hypothesis import given
from hypothesis import strategies as st

from isic.core.storages.s3 import CacheableCloudFrontStorage


@given(t_now=st.datetimes(timezones=st.just(None)))
def test_expiration_time(t_now):
    t_now = timezone.make_aware(t_now)
    t_next = CacheableCloudFrontStorage.next_expiration_time(t_now)
    expires_in = t_next - t_now
    assert expires_in > timedelta(days=6)
    assert expires_in <= timedelta(days=7)
