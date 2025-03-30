FROM python:3.12-slim
# Install system librarires for Python packages:
# * libmagic1
# * psycopg2
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libmagic1 libpq-dev gcc libc6-dev git curl && \
    rm -rf /var/lib/apt/lists/* && echo "hi2"

RUN pip install uv

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1





# Only copy the setup.py, it will still force all install_requires to be installed,
# but find_packages() will find nothing (which is fine). When Docker Compose mounts the real source
# over top of this directory, the .egg-link in site-packages resolves to the mounted directory
# and all package modules are importable.
COPY ./setup.py /opt/django-project/setup.py
RUN uv venv -p 3.12 /opt/django-project/.venv
RUN uv pip install --system \
                   --find-links https://girder.github.io/large_image_wheels \
                   --editable \
                   /opt/django-project[dev,test,type]

# Use a directory name which will never be an import name, as isort considers this as first-party.
WORKDIR /opt/django-project


ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

#RUN chown -R $USERNAME:$USERNAME /opt/django-project

USER $USERNAME
