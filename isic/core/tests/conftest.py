import functools

from django.contrib.auth.models import User
from django.db.models.signals import post_save
import pytest

from isic.core.guardian_permissions import (
    contributor_save_assign_perms,
    image_save_assign_perms,
    image_share_save_assign_perms,
    user_save_assign_groups,
)
from isic.core.models.image import Image, ImageShare
from isic.ingest.models.contributor import Contributor
from isic.ingest.services.accession.review import update_or_create_accession_review


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

        update_or_create_accession_review(
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

        update_or_create_accession_review(
            accession=accession,
            reviewer=user,
            reviewed_at=accession.created,
            value=True,
        )

        return functools.partial(image_factory, accession=accession, public=False)

    return inner


@pytest.fixture
def _mock_datacite_create_draft_doi(mocker):
    mocker.patch("isic.core.services.collection.doi._datacite_create_draft_doi")


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


@pytest.fixture
def suppress_post_save_signals():
    signals_and_senders = [
        (user_save_assign_groups, User),
        (image_save_assign_perms, Image),
        (image_share_save_assign_perms, ImageShare),
        (contributor_save_assign_perms, Contributor),
    ]
    for signal, sender in signals_and_senders:
        post_save.disconnect(signal, sender=sender)
    yield
    for signal, sender in signals_and_senders:
        post_save.connect(signal, sender=sender)
