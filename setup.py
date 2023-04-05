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
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python",
    ],
    python_requires=">=3.10",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "celery",
        "deepdiff",
        "django<4.2",
        "django-allauth",
        "django-click",
        "django-configurations[database,email]",
        "django-extensions",
        "django-filter",
        "django-girder-utils",
        "django-json-widget",
        "django-nested-admin",
        # v2 removed OOB support
        # https://github.com/jazzband/django-oauth-toolkit/pull/1124
        "django-oauth-toolkit<2.0.0",
        "django-object-actions",
        "django-spurl",
        "django-widget-tweaks",
        "djangorestframework",
        "drf-yasg",
        "google-api-python-client",
        "hashids",
        "isic-metadata>=0.0.6",
        "jaro-winkler",
        "more_itertools",
        "oauth2client",
        "opensearch-py",
        "pandas",
        "passlib[bcrypt]",
        "Pillow",
        "pycountry",
        "pydantic",
        "pymongo",
        "pyparsing",
        "python-magic",
        "requests",
        "tenacity",
        "zipfile-deflate64",
        # Production-only
        "django-composed-configuration[prod]>=0.21.0",
        "django-s3-file-field[boto3]",
        "gunicorn",
    ],
    extras_require={
        "dev": [
            "django-composed-configuration[dev]",
            "django-debug-toolbar",
            "django-s3-file-field[minio]",
            "ipython",
            "tox",
            "werkzeug",
        ]
    },
)
