import pytest


@pytest.fixture
def public_study(study_factory, user_factory):
    creator = user_factory()
    owners = [creator] + [user_factory() for _ in range(2)]
    return study_factory(public=True, creator=creator, owners=owners)


@pytest.fixture
def private_study(study_factory, user_factory):
    creator = user_factory()
    owners = [creator] + [user_factory() for _ in range(2)]
    return study_factory(public=False, creator=creator, owners=owners)


@pytest.fixture
def private_study_and_guest(private_study, user_factory):
    return private_study, user_factory()


@pytest.fixture
def private_study_and_annotator(private_study, user_factory, study_task_factory):
    u = user_factory()
    study_task_factory(annotator=u, study=private_study)
    return private_study, u


@pytest.fixture
def private_study_and_owner(private_study):
    return private_study, private_study.owners.first()


@pytest.fixture
def private_study_with_responses(study_factory, user_factory, response_factory):
    # create a scenario for testing that a user can only see their responses and
    # not another annotators.
    study = study_factory(public=False)
    u1, u2 = user_factory(), user_factory()
    response_factory(
        annotation__annotator=u1,
        annotation__study=study,
        annotation__task__annotator=u1,
        annotation__task__study=study,
    )
    response_factory(
        annotation__annotator=u2,
        annotation__study=study,
        annotation__task__annotator=u2,
        annotation__task__study=study,
    )
    return study, u1, u2


@pytest.fixture
def study_task_with_user(study_task_factory, user_factory):
    u = user_factory()
    study_task = study_task_factory(annotator=u)
    return study_task
