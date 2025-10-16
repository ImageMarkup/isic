FROM node:16.20-alpine

# "@parcel/watcher" requires "node-gyp", which requires Python to build for some architectures
RUN apk update && apk add g++ make python3

WORKDIR /opt/django-project

RUN \
  --mount=type=cache,target=/root/.npm \
  --mount=source=package.json,target=package.json \
  --mount=source=package-lock.json,target=package-lock.json \
  npm ci
