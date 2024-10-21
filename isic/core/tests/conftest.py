import functools

import pytest

from isic.ingest.services.accession.review import accession_review_update_or_create


@pytest.fixture()
def private_collection(collection_factory):
    return collection_factory(public=False)


@pytest.fixture()
def public_collection(collection_factory):
    return collection_factory(public=True)


@pytest.fixture()
def other_contributor(user_factory, contributor_factory):
    user = user_factory()
    return contributor_factory(owners=[user])


@pytest.fixture()
def contributors(contributor, other_contributor):
    return [contributor, other_contributor]


@pytest.fixture()
def private_image(reviewed_image_factory):
    return reviewed_image_factory()(public=False)


@pytest.fixture()
def public_image(reviewed_image_factory):
    return reviewed_image_factory()(public=True)


@pytest.fixture()
def reviewed_image_factory(image_factory, accession_factory, user):
    def inner():
        accession = accession_factory()

        accession_review_update_or_create(
            accession=accession,
            reviewer=user,
            reviewed_at=accession.created,
            value=True,
        )

        return functools.partial(image_factory, accession=accession)

    return inner
