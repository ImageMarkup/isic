#!/bin/bash
set -exu

uv run ./manage.py migrate
DJANGO_SUPERUSER_PASSWORD=password uv run ./manage.py createsuperuser --noinput --email 'admin@kitware.com' --username 'admin@kitware.com' || echo "Superuser already exists"
uv run ./manage.py set_fake_passwords

echo 'alias serve="uv run ./manage.py runserver 0.0.0.0:8000"' >> ~/.bashrc
