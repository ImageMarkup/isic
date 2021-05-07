#!/usr/bin/env bash
set -exuo pipefail

export HEROKU_APP=isic

docker-compose exec postgres bash -c "PGPASSWORD=postgres dropdb --host localhost --username postgres --if-exists django && createdb --host localhost --username postgres django"

docker-compose exec postgres bash -c \
"pg_dump --format=custom --no-privileges $(heroku config:get DATABASE_URL)\
 | PGPASSWORD=postgres pg_restore --host localhost --username postgres --format=custom --no-privileges --no-owner --dbname=django"

docker-compose restart postgres
