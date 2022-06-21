from django.urls.base import reverse
from django.utils import timezone
import pytest
from pytest_lazyfixture import lazy_fixture

from isic.studies.models import StudyTask


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
def test_study_list_objects_owner_permissions(authenticated_client, private_study, public_study):
    for owner in private_study.owners.all():
        authenticated_client.force_login(owner)
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
    'client_,status',
    [
        [lazy_fixture('client'), 302],
        [lazy_fixture('authenticated_client'), 403],
        [lazy_fixture('staff_client'), 200],
    ],
)
def test_study_detail_objects_public_permissions(client_, status, private_study):
    r = client_.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == status


@pytest.mark.django_db
def test_study_detail_objects_creator_permissions(authenticated_client, private_study):
    for owner in private_study.owners.all():
        authenticated_client.force_login(owner)
        r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
        assert r.status_code == 200


@pytest.mark.django_db
def test_study_detail_objects_annotator_permissions(
    user, authenticated_client, private_study, image
):
    r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == 403

    # Test that a user with a studytask in a study can see the study even if it's private
    StudyTask.objects.create(study=private_study, annotator=user, image=image)

    r = authenticated_client.get(reverse('study-detail', args=[private_study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_,status',
    [
        [lazy_fixture('client'), 302],
        [lazy_fixture('authenticated_client'), 403],
        [lazy_fixture('staff_client'), 200],
    ],
)
def test_study_view_responses_csv_private_study_permissions(client_, status, private_study):
    r = client_.get(reverse('study-download-responses', args=[private_study.pk]))

    assert r.status_code == status


@pytest.mark.django_db
def test_study_view_responses_csv_private_study_owner_permissions(client, private_study):
    for owner in private_study.owners.all():
        client.force_login(owner)
        r = client.get(reverse('study-download-responses', args=[private_study.pk]))
        assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_',
    [
        lazy_fixture('client'),
        lazy_fixture('authenticated_client'),
        lazy_fixture('staff_client'),
    ],
)
def test_study_view_responses_csv_public_permissions(client_, public_study):
    r = client_.get(reverse('study-download-responses', args=[public_study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('client_', [lazy_fixture('client'), lazy_fixture('authenticated_client')])
def test_study_task_detail_preview_public(client_, public_study):
    r = client_.get(reverse('study-task-detail-preview', args=[public_study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'study_and_user,status',
    [
        [lazy_fixture('private_study_and_guest'), 403],
        [lazy_fixture('private_study_and_owner'), 200],
        [lazy_fixture('private_study_and_annotator'), 200],
    ],
)
def test_study_task_detail_preview_private(client, study_and_user, status):
    client.force_login(study_and_user[1])
    r = client.get(reverse('study-task-detail-preview', args=[study_and_user[0].pk]))
    assert r.status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_,status',
    [
        [lazy_fixture('client'), 302],
        [lazy_fixture('authenticated_client'), 403],
        [lazy_fixture('staff_client'), 200],
    ],
)
def test_study_task_detail_invisible_to_non_annotators(client_, status, study_task_with_user):
    r = client_.get(reverse('study-task-detail', args=[study_task_with_user.pk]))
    assert r.status_code == status


@pytest.mark.django_db
def test_study_task_detail_visible_to_annotator(client, user, study_task_factory):
    study_task = study_task_factory(annotator=user)
    client.force_login(user)
    r = client.get(reverse('study-task-detail', args=[study_task.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_task_detail_visible_to_study_owner(client, user, study_task_factory, user_factory):
    # make sure the annotator is a different user so the test doesn't accidentally pass
    study_task = study_task_factory(annotator=user_factory(), study__creator=user)
    client.force_login(user)
    r = client.get(reverse('study-task-detail', args=[study_task.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_task_detail_shows_private_images_to_annotator(
    user, image_factory, study_task_factory
):
    # This test is more about documenting a policy decision which allows a user to see
    # an image via a study task, but not directly.
    # This allows a person to conduct a study on images they haven't explicitly shared.
    image = image_factory(public=False)
    study_task = study_task_factory(image=image, annotator=user)

    assert not user.has_perm('core.view_image', image)
    assert user.has_perm('studies.view_study_task', study_task)


@pytest.mark.skip('Migrating model so test is temporarily broken')
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
    assert r.status_code == 302  # TODO: Should be 404

    r = authenticated_client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 302  # TODO: Should be 404

    r = staff_client.get(reverse('annotation-detail', args=[annotation.pk]))
    assert r.status_code == 200


@pytest.fixture
def study_scenario(user_factory, study_factory, question_factory, question_choice_factory):
    user = user_factory()
    study = study_factory(creator=user, public=False)
    question = question_factory()
    choice = question_choice_factory(question=question)
    question.choices.add(choice)
    study.questions.add(question, through_defaults={'required': True})
    return study, question, choice


@pytest.mark.django_db
def test_study_task_detail_post(client, study_scenario, study_task_factory, user_factory):
    study, question, choice = study_scenario
    user = user_factory()
    study_task = study_task_factory(study=study, annotator=user)
    client.force_login(study_task.annotator)
    client.post(
        reverse('study-task-detail', args=[study_task.pk]),
        {'start_time': timezone.now(), question.pk: choice.pk},
    )
    assert study_task.annotation

    response = study_task.annotation.responses.first()
    assert response.annotation.annotator == user
    assert response.question == question
    assert response.choice == choice


@pytest.mark.django_db
def test_study_api_list_creator_permissions(
    api_client, study_scenario, study_factory, user_factory
):
    study_factory(creator=user_factory(), public=False)
    api_client.force_login(study_scenario[0].creator)
    r = api_client.get('/api/v2/studies/')
    assert r.data['count'] == 1
    assert r.data['results'][0]['id'] == study_scenario[0].id


@pytest.mark.django_db
def test_study_api_list_owners_permissions(api_client, study_scenario, study_factory, user_factory):
    study_factory(creator=user_factory(), public=False, owners=[study_scenario[0].creator])
    api_client.force_login(study_scenario[0].creator)
    r = api_client.get('/api/v2/studies/')
    assert r.data['count'] == 2


# @pytest.mark.django_db
# @pytest.mark.parametrize(
#     'client_,url,',
#     [
#         lazy_fixture('client'),
#         lazy_fixture('authenticated_client'),
#         lazy_fixture('staff_client'),
#     ],
# )
# def test_study_api_detail_permissions(client, study_scenario, study_task_factory, user_factory):
#     pass


@pytest.mark.django_db
@pytest.mark.parametrize('method,path', [['post', 'set-tasks'], ['delete', 'delete-tasks']])
def test_study_api_modify_tasks_on_study_with_responses_permissions(
    api_client, private_study_with_responses, method, path
):
    study = private_study_with_responses[0]
    api_client.force_login(study.creator)
    r = api_client.generic(method, f'/api/v2/studies/{study.pk}/{path}/')
    assert r.status_code == 409


@pytest.mark.django_db
@pytest.mark.parametrize('method,path', [['post', 'set-tasks'], ['delete', 'delete-tasks']])
def test_study_api_modify_tasks_on_someone_elses_study_permissions(
    api_client, user_factory, public_study, method, path
):
    api_client.force_login(user_factory())
    r = api_client.generic(method, f'/api/v2/studies/{public_study.pk}/{path}/')
    assert r.status_code == 403
