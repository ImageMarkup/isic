import logging

from cachalot.signals import post_invalidation
from django.conf import settings

logger = logging.getLogger(__name__)


def invalidation_debug(sender: str, **kwargs):
    if hasattr(settings, "CACHALOT_ENABLED") and settings.CACHALOT_ENABLED:
        logger.info("Invalidated cache for %s:%s", kwargs["db_alias"], sender)


post_invalidation.connect(invalidation_debug)
