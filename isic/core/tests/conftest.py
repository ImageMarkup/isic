import functools

import pytest

from isic.ingest.services.accession.review import accession_review_update_or_create


@pytest.fixture
def private_collection(collection_factory):
    return collection_factory(public=False)


@pytest.fixture
def public_collection(collection_factory):
    return collection_factory(public=True)


@pytest.fixture
def other_contributor(user_factory, contributor_factory):
    user = user_factory()
    return contributor_factory(owners=[user])


@pytest.fixture
def contributors(contributor, other_contributor):
    return [contributor, other_contributor]


@pytest.fixture
def public_image(public_reviewed_image_factory):
    return public_reviewed_image_factory()()


@pytest.fixture
def private_image(private_reviewed_image_factory):
    return private_reviewed_image_factory()()


@pytest.fixture
def public_reviewed_image_factory(image_factory, accession_factory, user):
    def inner():
        accession = accession_factory(public=True)

        accession_review_update_or_create(
            accession=accession,
            reviewer=user,
            reviewed_at=accession.created,
            value=True,
        )

        return functools.partial(image_factory, accession=accession, public=True)

    return inner


@pytest.fixture
def private_reviewed_image_factory(image_factory, accession_factory, user):
    def inner():
        accession = accession_factory(public=False)

        accession_review_update_or_create(
            accession=accession,
            reviewer=user,
            reviewed_at=accession.created,
            value=True,
        )

        return functools.partial(image_factory, accession=accession, public=False)

    return inner


@pytest.fixture
def mock_fetch_doi_schema_org_dataset(mocker):
    return mocker.patch(
        "isic.core.tasks._fetch_doi_schema_org_dataset",
        return_value={"@type": "Dataset", "name": "fake dataset"},
    )


@pytest.fixture
def mock_fetch_doi_citations(mocker):
    return mocker.patch(
        "isic.core.tasks._fetch_doi_citations",
        return_value={"apa": "fake citation", "chicago": "fake citation"},
    )
