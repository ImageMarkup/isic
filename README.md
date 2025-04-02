# ISIC

## Develop with Docker (recommended quickstart)
This is the simplest configuration for developers to start with.

### Initial Setup
1. Run `docker-compose run --rm django uv run ./manage.py migrate`
1. Run `docker-compose run --rm django uv run ./manage.py createsuperuser`
   and follow the prompts to create your own user

### Run Application
1. Run `docker-compose up`
1. Access the site, starting at http://localhost:8000/admin/
1. When finished, use `Ctrl+C`

### Application Maintenance
Occasionally, new package dependencies or schema changes will necessitate
maintenance. To non-destructively update your development stack at any time:
1. Run `docker-compose pull`
1. Run `docker-compose build --pull --no-cache`
1. Run `docker-compose run --rm django uv run ./manage.py migrate`

## Develop Natively (advanced)
This configuration still uses Docker to run attached services in the background,
but allows developers to run Python code on their native system.

### Initial Setup
1. Run `docker-compose -f ./docker-compose.yml up -d`
1. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/)
1. Run `export UV_ENV_FILE=./dev/.env.docker-compose-native`
1. Run `uv run ./manage.py migrate`
1. Run `uv run ./manage.py createsuperuser` and follow the prompts to create your own user
1. Run `yarn && yarn build` (must be re-run whenever styles change)

### Run Application
1. Ensure `docker compose -f ./docker-compose.yml up -d` is still active
1. Run: `UV_ENV_FILE=./dev/.env.docker-compose-native uv run ./manage.py runserver`
1. Run in a separate terminal: `UV_ENV_FILE=./dev/.env.docker-compose-native uv run celery --app isic.celery worker --loglevel INFO --without-heartbeat`
1. Run in a separate terminal: `UV_ENV_FILE=./dev/.env.docker-compose-native uv run celery --app isic.celery beat --loglevel INFO --without-heartbeat`
1. When finished, run `docker-compose stop`

## Remap Service Ports (optional)
Attached services may be exposed to the host system via alternative ports. Developers who work
on multiple software projects concurrently may find this helpful to avoid port conflicts.

To do so, before running any `docker-compose` commands, set any of the environment variables:
* `DOCKER_POSTGRES_PORT`
* `DOCKER_RABBITMQ_PORT`
* `DOCKER_MINIO_PORT`

The Django server must be informed about the changes:
* When running the "Develop with Docker" configuration, override the environment variables:
  * `DJANGO_MINIO_STORAGE_MEDIA_URL`, using the port from `DOCKER_MINIO_PORT`.
* When running the "Develop Natively" configuration, override the environment variables:
  * `DJANGO_DATABASE_URL`, using the port from `DOCKER_POSTGRES_PORT`
  * `DJANGO_CELERY_BROKER_URL`, using the port from `DOCKER_RABBITMQ_PORT`
  * `DJANGO_MINIO_STORAGE_ENDPOINT`, using the port from `DOCKER_MINIO_PORT`

Since most of Django's environment variables contain additional content, use the values from
the appropriate `dev/.env.docker-compose*` file as a baseline for overrides.

## Testing
### Initial Setup
tox is used to manage the execution of all tests.
[Install `uv`](https://docs.astral.sh/uv/getting-started/installation/) and run tox with
`uvx tox ...`.

When running the "Develop with Docker" configuration, all tox commands must be run as
`docker-compose run --rm django uvx tox`; extra arguments may also be appended to this form.

### Running Tests
Run `uvx tox` to launch the full test suite.

Individual test environments may be selectively run.
This also allows additional options to be be added.
Useful sub-commands include:
* `uvx tox -e lint`: Run only the style checks
* `uvx tox -e type`: Run only the type checks
* `uvx tox -e test`: Run only the pytest-driven tests

To automatically reformat all code to comply with
some (but not all) of the style checks, run `uvx tox -e format`.
