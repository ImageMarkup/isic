#!/bin/bash
set -eux

echo -e "--find-links https://girder.github.io/large_image_wheels\n" > requirements.txt

pip freeze --exclude isic >> requirements.txt
