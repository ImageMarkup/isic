FROM ghcr.io/astral-sh/uv:debian
# Install system librarires for Python packages:
# * libmagic1
# * psycopg2
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libmagic1 libpq-dev gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/django-project

COPY ./pyproject.toml /opt/django-project/pyproject.toml
COPY ./uv.toml /opt/django-project/uv.toml

RUN uv sync --compile-bytecode --no-cache
