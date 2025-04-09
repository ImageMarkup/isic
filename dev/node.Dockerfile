FROM node:bullseye-slim

# "@parcel/watcher" requires "node-gyp", which requires Python to build for some architectures
RUN apt-get update && apt-get install -y g++ make python3

USER node
