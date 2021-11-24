from django.urls.base import reverse
import pytest
from pytest_lazyfixture import lazy_fixture

from isic.studies.models import StudyTask


@pytest.fixture
def public_study(study_factory):
    return study_factory(public=True)


@pytest.fixture
def private_study(study_factory):
    return study_factory(public=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_',
    [
        lazy_fixture('client'),
        lazy_fixture('authenticated_client'),
        lazy_fixture('staff_client'),
    ],
)
def test_study_list_permissions(client_):
    r = client_.get(reverse('study-list'))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_,can_see_private',
    [
        [lazy_fixture('client'), False],
        [lazy_fixture('authenticated_client'), False],
        [lazy_fixture('staff_client'), True],
    ],
)
def test_study_list_objects_public_permissions(
    client_, can_see_private, private_study, public_study
):
    r = client_.get(reverse('study-list'))
    assert r.status_code == 200
    assert public_study in r.context['studies']

    if can_see_private:
        assert private_study in r.context['studies']
    else:
        assert private_study not in r.context['studies']


@pytest.mark.django_db
def test_study_list_objects_creator_permissions(authenticated_client, private_study, public_study):
    authenticated_client.force_login(private_study.creator)
    r = authenticated_client.get(reverse('study-list'))
    assert r.status_code == 200
    assert public_study in r.context['studies']
    assert private_study in r.context['studies']


@pytest.mark.django_db
def test_study_list_objects_annotator_permissions(
    user, authenticated_client, private_study, public_study, image
):
    r = authenticated_client.get(reverse('study-list'))
    assert r.status_code == 200
    assert public_study in r.context['studies']
    assert private_study not in r.context['studies']

    # Test that a user with a studytask in a study can see the study even if it's private
    StudyTask.objects.create(study=private_study, annotator=user, image=image)

    r = authenticated_client.get(reverse('study-list'))
    assert r.status_code == 200
    assert public_study in r.context['studies']
    assert private_study in r.context['studies']


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_,can_see_private',
    [
        [lazy_fixture('client'), False],
        [lazy_fixture('authenticated_client'), False],
        [lazy_fixture('staff_client'), True],
    ],
)
def test_study_detail_objects_public_permissions(client_, can_see_private, private_study):
    r = client_.get(reverse('study-detail', args=[private_study.pk]))

    if can_see_private:
        assert r.status_code == 200
    else:
        assert r.status_code == 404


@pytest.mark.django_db
def test_study_detail_objects_creator_permissions(authenticated_client, private_study):
    authenticated_client.force_login(private_study.creator)
    r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_detail_objects_annotator_permissions(
    user, authenticated_client, private_study, image
):
    r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == 404

    # Test that a user with a studytask in a study can see the study even if it's private
    StudyTask.objects.create(study=private_study, annotator=user, image=image)

    r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_view_mask_permissions(client, authenticated_client, staff_client, markup):
    r = client.get(reverse('view-mask', args=[markup.pk]))
    assert r.status_code == 302

    # TODO: markup creators can't see their own masks
    client.force_login(markup.annotation.annotator)
    r = client.get(reverse('view-mask', args=[markup.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('view-mask', args=[markup.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse('view-mask', args=[markup.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_annotation_detail_permissions(client, authenticated_client, staff_client, annotation):
    r = client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 302

    # TODO: annotation creators can't see their own annotations
    client.force_login(annotation.annotator)
    r = client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 200
