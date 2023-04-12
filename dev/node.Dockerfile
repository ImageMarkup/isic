FROM node:16.20-alpine

# "@parcel/watcher" requires "node-gyp", which requires Python to build for some architectures
RUN apk update && apk add g++ make python3

# Copy these for the same reason as setup.py; they are needed for installation, but will be mounted
# over in the container.
COPY ./package.json /opt/django-project/package.json
COPY ./yarn.lock /opt/django-project/yarn.lock
RUN yarn --cwd /opt/django-project install --frozen-lockfile

WORKDIR /opt/django-project
