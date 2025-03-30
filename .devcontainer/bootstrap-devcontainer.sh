#!/bin/bash
set -exu

block_until_http () {
   echo "waiting for $1 to be available.."
   set +x
   while ! curl --silent --output /dev/null $1; do
      sleep 0.1
   done
   set -x
}

block_until_http 'elasticsearch:9200/_cluster/health'

./manage.py migrate
DJANGO_SUPERUSER_PASSWORD=password ./manage.py createsuperuser --noinput --email 'admin@kitware.com' --username 'admin@kitware.com'
./manage.py set_fake_passwords

echo 'alias serve="./manage.py runserver 0.0.0.0:8000"' >> ~/.bashrc
