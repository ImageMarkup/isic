release: ./manage.py migrate
web: gunicorn --bind 0.0.0.0:$PORT isic.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery worker --app isic.celery --loglevel info --without-heartbeat
