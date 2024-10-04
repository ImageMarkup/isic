#!/bin/bash
set -e

celery --app isic.celery worker \
    --loglevel INFO \
    --without-heartbeat \
    --concurrency 2 \
    --queues celery
