import os

from celery import Celery
import celery.app.trace
from celery.contrib.django.task import DjangoTask

celery.app.trace.LOG_RECEIVED = """\
Task %(name)s[%(id)s] received: (%(args)s, %(kwargs)s)\
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "isic.settings.production")


# Using a string config_source means the worker doesn't have to serialize
# the configuration object to child processes.
app = Celery(
    task_cls=DjangoTask,
    config_source="django.conf:settings",
    namespace="CELERY",
)

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
