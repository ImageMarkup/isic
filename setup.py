from pathlib import Path

from setuptools import find_packages, setup

readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    with readme_file.open() as f:
        long_description = f.read()
else:
    # When this is first installed in development Docker, README.md is not available
    long_description = ""

setup(
    name="isic",
    version="0.1.0",
    description="",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache 2.0",
    url="https://github.com/ImageMarkup/isic",
    project_urls={
        "Bug Reports": "https://github.com/ImageMarkup/isic/issues",
        "Source": "https://github.com/ImageMarkup/isic",
    },
    author="Kitware, Inc.",
    author_email="kitware@kitware.com",
    keywords="",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Framework :: Django :: 3.0",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python",
    ],
    python_requires=">=3.12",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "bcrypt",
        "celery>=5.4.0",
        "deepdiff",
        "dj_email_url",
        "dj-database-url",
        "django-allauth>=0.56.0",
        "django-auth-style",
        "django-cachalot>=2.7.0",
        "django-cache-url",
        "django-click",
        "django-cors-headers",
        "django-extensions",
        "django-filter",
        "django-girder-utils",
        "django-json-widget",
        "django-ninja>=1.0a3",
        # v2 removed OOB support
        # https://github.com/jazzband/django-oauth-toolkit/pull/1124
        "django-oauth-toolkit<2.0.0",
        "django-object-actions",
        "django-redis",
        "django-storages>1.14.2",
        "django-stubs-ext",
        "django-widget-tweaks",
        "django[argon2]>=5.1,<6",
        "gdal",
        "google-analytics-data",
        "hashids",
        "hiredis",
        "isic-metadata>=4.1.0",
        "jaro-winkler",
        "oauth2client",
        "opensearch-py",
        "pandas",
        "Pillow",
        "psycopg",
        "pycountry",
        "pydantic",
        "pymongo",
        "pyparsing",
        "python-magic",
        "redis",
        "requests",
        "rich",
        "sentry-sdk[pure_eval]",
        "tenacity",
        "whitenoise[brotli]",
        "zipfile-deflate64",
        # Production-only
        "django-s3-file-field[s3]>=1",
        "gunicorn",
    ],
    extras_require={
        "dev": [
            "django-debug-toolbar",
            "django-fastdev",
            "django-s3-file-field[minio]>=1",
            "ipython",
            "memray",
            "pyinstrument",
            "tox",
            "werkzeug",
        ],
        "test": [
            "coverage[toml]",
            "django-fastdev",
            "factory-boy",
            "hypothesis",
            "pytest",
            "pytest-cov",
            "pytest-django",
            "pytest-factoryboy",
            "pytest-lazy-fixtures",
            "pytest-mock",
            # Used in an adhoc manner during development
            "pytest-random-order",
            "pytest-repeat",
        ],
        "type": [
            "django-stubs[compatible-mypy]",
            "mypy",
            "types-requests",
        ],
    },
)
