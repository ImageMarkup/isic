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
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python",
    ],
    python_requires=">=3.11",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "celery",
        "deepdiff",
        "django>4.2,<5",
        "django-allauth>=0.56.0",
        "django-click",
        "django-configurations[database,email]",
        "django-extensions",
        "django-filter",
        "django-girder-utils",
        "django-json-widget",
        "django-ninja>=1.0a3",
        # v2 removed OOB support
        # https://github.com/jazzband/django-oauth-toolkit/pull/1124
        "django-oauth-toolkit<2.0.0",
        "django-object-actions",
        "django-spurl",
        "django-storages>=1.14.2",
        "django-widget-tweaks",
        "google-analytics-data",
        "hashids",
        "isic-metadata>=1.9.1",
        "jaro-winkler",
        "more_itertools",
        "oauth2client",
        "opensearch-py",
        "pandas<2.1.0",
        "passlib[bcrypt]",
        "Pillow",
        "pycountry",
        "pydantic",
        "pymongo",
        "pyparsing",
        "python-magic",
        "requests",
        "sentry-sdk[pure_eval]",
        "tenacity",
        "zipfile-deflate64",
        # Production-only
        "django_composed_configuration",
        "django-s3-file-field[s3]>=1",
        "gunicorn",
    ],
    extras_require={
        "dev": [
            "django-composed-configuration[dev]",
            "django-debug-toolbar",
            "django-fastdev",
            "django-s3-file-field[minio]>=1",
            "ipython",
            "memray",
            "pyinstrument",
            "tox",
            "werkzeug",
        ]
    },
)
