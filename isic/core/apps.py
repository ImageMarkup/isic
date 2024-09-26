from django.apps import AppConfig

from .signals import post_invalidation  # noqa: F401


class CoreConfig(AppConfig):
    name = "isic.core"
    verbose_name = "ISIC: Core"
