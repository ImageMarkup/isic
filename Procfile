release: ./manage.py migrate
web: gunicorn --bind 0.0.0.0:$PORT isic.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery --app isic.celery worker --loglevel INFO --without-heartbeat --concurrency 2
