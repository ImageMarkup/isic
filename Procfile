release: ./manage.py migrate
# certain streaming endpoints (like cohort-all-metadata) require more time.
# set the request line limit to match heroku:
# https://devcenter.heroku.com/articles/http-routing#http-validation-and-restrictions
# long request lines are useful for long DSL search queries
web: gunicorn --timeout 120 --limit-request-line 8192 --bind 0.0.0.0:$PORT isic.wsgi
worker: REMAP_SIGTERM=SIGQUIT celery --app isic.celery worker --loglevel INFO --without-heartbeat --concurrency 2
beat: REMAP_SIGTERM=SIGQUIT celery --app isic.celery beat --loglevel INFO
