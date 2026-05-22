#!/bin/bash
set -e

celery --app isic.celery worker \
    --loglevel INFO \
    --without-mingle \
    --without-heartbeat \
    --without-gossip \
    --concurrency 2 \
    --queues s3-log-processing,stats-aggregation,es-indexing
