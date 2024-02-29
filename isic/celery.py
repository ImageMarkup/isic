import os

from celery import Celery, Task
import celery.app.trace
import configurations.importer
from django.db import transaction

celery.app.trace.LOG_RECEIVED = """\
Task %(name)s[%(id)s] received: (%(args)s, %(kwargs)s)\
"""

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

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
