from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import renderers


class JSONRenderer(renderers.JSONRenderer):
    # Unlike DRF's encoder, DjangoJSONEncoder renders datetimes with millisecond precision and
    # decimals as strings, which is what API clients expect.
    encoder_class = DjangoJSONEncoder
