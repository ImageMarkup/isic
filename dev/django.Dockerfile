FROM ghcr.io/astral-sh/uv:debian
# Install system librarires for Python packages:
# * libmagic1
# * psycopg2
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libmagic1 libpq-dev gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED 1

# Docker Compose will also mount this at runtime.
RUN --mount=source=.,target=. \
    uv sync --compile-bytecode --no-cache
