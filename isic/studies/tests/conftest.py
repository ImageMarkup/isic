import pytest


@pytest.fixture()
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
        choice=None,
        value=5,
    )
    response_factory(
        annotation__annotator=u2,
        annotation__study=study,
        annotation__task__annotator=u2,
        annotation__task__study=study,
        choice=None,
        value=5,
    )
    return study, u1, u2
