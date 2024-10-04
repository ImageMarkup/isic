#!/bin/bash
set -e

celery --app isic.celery worker \
    --loglevel INFO \
    --without-heartbeat \
    --concurrency 2 \
    --queues s3-log-processing,stats-aggregation,es-indexing
