from .base import *

SECRET_KEY = "insecure-secret"
ALLOWED_HOSTS = ["testserver"]

# Kept apart from the database the test suite creates.
DATABASES["default"]["TEST"] = {"NAME": "test_isic_benchmark"}

# Every request should do its full work.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
CACHALOT_ENABLED = False

# A migration creates the indices, so keep them apart from the development indices.
ISIC_ELASTICSEARCH_IMAGES_INDEX = "benchmark-isic"
ISIC_ELASTICSEARCH_LESIONS_INDEX = "benchmark-isic-lesions"

# Production storage backends. Unsigned S3 urls are built locally, so no credentials or network
# are needed.
AWS_S3_REGION_NAME = "us-east-1"
AWS_S3_ACCESS_KEY_ID = "benchmark"
AWS_S3_SECRET_ACCESS_KEY = "benchmark"
STORAGES["default"] = {
    "BACKEND": "isic.core.storages.s3.IsicS3StaticStorage",
    "OPTIONS": {"bucket_name": "isic-storage"},
}
STORAGES["sponsored"] = {
    "BACKEND": "isic.core.storages.s3.IsicS3StaticStorage",
    "OPTIONS": {"bucket_name": "isic-archive"},
}
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
