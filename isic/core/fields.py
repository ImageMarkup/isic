from django.core.validators import RegexValidator
from django.db import models

ISIC_ID_VALIDATOR = RegexValidator(r'^ISIC_[0-9]{7}$')


class IsicIdField(models.CharField):
    description = 'An isic identifier (e.g. ISIC_0123456)'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 12)
        kwargs.setdefault('unique', True)
        kwargs.setdefault('verbose_name', 'ISIC ID')
        kwargs.setdefault('validators', [ISIC_ID_VALIDATOR])
        super().__init__(*args, **kwargs)
