release: ./manage.py migrate
# certain streaming endpoints (like cohort-all-metadata) require more time
web: gunicorn --timeout 120 --bind 0.0.0.0:$PORT isic.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery --app isic.celery worker --loglevel INFO --without-heartbeat --concurrency 2
beat: REMAP_SIGTERM=SIGQUIT celery --app isic.celery beat --loglevel INFO
