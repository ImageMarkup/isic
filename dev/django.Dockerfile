FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04
# Install system librarires for Python packages:
# * libmagic1
# * psycopg2
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libmagic1 libpq-dev gcc libc6-dev git python3-dev && \
    rm -rf /var/lib/apt/lists/*


RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN mv /root/.local/bin/uv /usr/local/bin/uv
RUN mv /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /opt/django-project
