import logging

from django.apps import AppConfig
from django.conf import settings
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration

from .signals import post_invalidation  # noqa: F401


class CoreConfig(AppConfig):
    name = "isic.core"
    verbose_name = "ISIC: Core"

    @staticmethod
    def _get_sentry_performance_sample_rate(*args, **kwargs) -> float:  # noqa: ARG004
        """
        Determine sample rate of sentry performance.

        Only sample 1% of common requests for performance monitoring, and all staff/admin requests
        since they're relatively low volume but high value. Also sample all infrequent tasks.
        """
        from isic.core.tasks import populate_collection_from_search_task
        from isic.ingest.tasks import (
            extract_zip_task,
            publish_cohort_task,
            update_metadata_task,
            validate_metadata_task,
        )
        from isic.studies.tasks import populate_study_tasks_task

        infrequent_tasks: list[str] = [
            task.name
            for task in [
                extract_zip_task,
                validate_metadata_task,
                update_metadata_task,
                publish_cohort_task,
                populate_collection_from_search_task,
                populate_study_tasks_task,
            ]
        ]

        if args and "wsgi_environ" in args[0]:
            path: str = args[0]["wsgi_environ"]["PATH_INFO"]
            if path.startswith(("/staff", "/admin")):
                return 1.0
        elif args and "celery_job" in args[0]:
            if args[0]["celery_job"]["task"] in infrequent_tasks:
                return 1.0

        return 0.01

    def ready(self):
        if hasattr(settings, "SENTRY_DSN"):
            sentry_sdk.init(
                # If a "dsn" is not explicitly passed, sentry_sdk will attempt to find the DSN in
                # the SENTRY_DSN environment variable; however, by pulling it from an explicit
                # setting, it can be overridden by downstream project settings.
                dsn=settings.SENTRY_DSN,
                environment=settings.SENTRY_ENVIRONMENT,
                release=settings.SENTRY_RELEASE,
                integrations=[
                    LoggingIntegration(level=logging.INFO, event_level=logging.WARNING),
                    DjangoIntegration(),
                    CeleryIntegration(),
                    PureEvalIntegration(),
                ],
                in_app_include=["isic"],
                # Send traces for non-exception events too
                attach_stacktrace=True,
                # Submit request User info from Django
                send_default_pii=True,
                traces_sampler=self._get_sentry_performance_sample_rate,
                profiles_sampler=self._get_sentry_performance_sample_rate,
            )
