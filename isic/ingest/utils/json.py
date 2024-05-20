from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder


class DecimalAwareJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)
