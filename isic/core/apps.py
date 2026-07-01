from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "isic.core"
    verbose_name = "ISIC Archive: Core"

    def ready(self):
        # Import to register permission assignment signals
        import isic.core.guardian_permissions  # noqa: F401
