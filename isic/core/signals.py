import logging

from cachalot.signals import post_invalidation

logger = logging.getLogger(__name__)


def invalidation_debug(sender: str, **kwargs):
    logger.info("Invalidated cache for %s:%s", kwargs["db_alias"], sender)


post_invalidation.connect(invalidation_debug)
