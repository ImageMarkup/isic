#!/bin/bash
set -e

# Procrastinate has no per-task timeout (no soft_time_limit/time_limit equivalent).
# This is a coarse backstop bounding any single statement issued by this process.
# libpq reads PGOPTIONS, and neither Django's connection params nor procrastinate's
# worker pool set "options", so both inherit it.
export PGOPTIONS="-c statement_timeout=30min"

# Fail at boot on a misconfigured worker rather than idling silently.
python ./manage.py procrastinate healthchecks

# Heroku sends SIGTERM then SIGKILLs 30 seconds later, so the graceful window has
# to fit inside that or it never actually runs.
python ./manage.py procrastinate worker \
    --queues default,stats-aggregation \
    --concurrency 2 \
    --shutdown-graceful-timeout 25
