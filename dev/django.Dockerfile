FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN mv /root/.local/bin/uv /usr/local/bin/uv
RUN mv /root/.local/bin/uvx /usr/local/bin/uvx

# Make Python more friendly to running in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

# Install system librarires for Python packages.
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER vscode

# The glob ensures COPY doesn't fail when the file doesn't exist
COPY dev/local-setup.sh* /tmp/
RUN if [ -f /tmp/local-setup.sh ]; then bash /tmp/local-setup.sh; fi

RUN mkdir /home/vscode/uv

WORKDIR /home/vscode/isic
