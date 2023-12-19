import logging
import os

from celery import Celery, Task, signals
import configurations.importer
from django.conf import settings
from django.db import transaction
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.pure_eval import PureEvalIntegration

from isic.core.apps import CoreConfig

os.environ["DJANGO_SETTINGS_MODULE"] = "isic.settings"
if not os.environ.get("DJANGO_CONFIGURATION"):
    raise ValueError('The environment variable "DJANGO_CONFIGURATION" must be set.')
configurations.importer.install()


class TransactionOnCommitTask(Task):
    def delay(self, *args, **kwargs):
        return transaction.on_commit(
            lambda: super(TransactionOnCommitTask, self).delay(*args, **kwargs)
        )


# Using a string config_source means the worker doesn't have to serialize
# the configuration object to child processes.
app = Celery(
    task_cls=TransactionOnCommitTask,
    config_source="django.conf:settings",
    namespace="CELERY",
)


@signals.celeryd_init.connect
def init_sentry(**kwargs):
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
                CeleryIntegration(monitor_beat_tasks=True),
                PureEvalIntegration(),
            ],
            in_app_include=["isic"],
            # Send traces for non-exception events too
            attach_stacktrace=True,
            # Submit request User info from Django
            send_default_pii=True,
            traces_sampler=CoreConfig._get_sentry_performance_sample_rate,
            profiles_sampler=CoreConfig._get_sentry_performance_sample_rate,
        )


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
