from django.urls.base import reverse
from django.utils import timezone
import pytest
from pytest_lazy_fixtures import lf

from isic.core.tests.factories import ImageFactory
from isic.factories import UserFactory
from isic.studies.tests.factories import (
    AnnotationFactory,
    MarkupFactory,
    QuestionFactory,
    StudyFactory,
    StudyTaskFactory,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_",
    [
        lf("client"),
        lf("authenticated_client"),
        lf("staff_client"),
    ],
)
def test_study_list_permissions(client_):
    r = client_.get(reverse("study-list"))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_",
    [
        lf("client"),
        lf("authenticated_client"),
    ],
)
def test_study_list_objects_permissions(client_):
    public_study = StudyFactory.create(public=True)
    private_study = StudyFactory.create(public=False)

    r = client_.get(reverse("study-list"))
    assert r.status_code == 200
    assert public_study in r.context["studies"]
    assert private_study not in r.context["studies"]


@pytest.mark.django_db
def test_study_list_objects_permissions_staff(staff_client):
    public_study = StudyFactory.create(public=True)
    private_study = StudyFactory.create(public=False)

    r = staff_client.get(reverse("study-list"))
    assert r.status_code == 200
    assert public_study in r.context["studies"]
    assert private_study in r.context["studies"]


@pytest.mark.django_db
def test_study_list_objects_permissions_owner(client):
    public_study = StudyFactory.create(public=True)
    private_study = StudyFactory.create(public=False)

    assert private_study.owners.exists()
    for owner in private_study.owners.all():
        client.force_login(owner)
        r = client.get(reverse("study-list"))
        assert r.status_code == 200
        assert public_study in r.context["studies"]
        assert private_study in r.context["studies"]


@pytest.mark.django_db
def test_study_list_objects_permissions_annotator(client):
    public_study = StudyFactory.create(public=True)
    private_study = StudyFactory.create(public=False)
    user = UserFactory.create()
    StudyTaskFactory.create(study=public_study, annotator=user)
    StudyTaskFactory.create(study=private_study, annotator=user)

    client.force_login(user)
    r = client.get(reverse("study-list"))
    assert r.status_code == 200
    assert public_study in r.context["studies"]
    assert private_study in r.context["studies"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view_name",
    [
        "study-edit",
        "study-add-annotators",
        "study-detail",
        "study-download-responses",
    ],
)
@pytest.mark.parametrize(
    ("client_", "status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 403),
        (lf("staff_client"), 200),
    ],
)
def test_study_view_permissions(view_name, client_, status):
    study = StudyFactory.create(public=False)

    r = client_.get(reverse(view_name, args=[study.pk]))
    assert r.status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view_name",
    [
        "study-edit",
        "study-add-annotators",
        "study-detail",
        "study-download-responses",
    ],
)
def test_study_view_permissions_owner(view_name, client):
    study = StudyFactory.create(public=False)

    assert study.owners.exists()
    for owner in study.owners.all():
        client.force_login(owner)
        r = client.get(reverse(view_name, args=[study.pk]))
        assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("view_name", "status"),
    [
        ("study-edit", 403),
        ("study-add-annotators", 403),
        ("study-detail", 200),
        ("study-download-responses", 403),
    ],
)
def test_study_view_permissions_annotator(view_name, status, client):
    study = StudyFactory.create(public=False)
    user = UserFactory.create()
    StudyTaskFactory.create(study=study, annotator=user)

    client.force_login(user)
    r = client.get(reverse(view_name, args=[study.pk]))
    assert r.status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_",
    [
        lf("client"),
        lf("authenticated_client"),
        lf("staff_client"),
    ],
)
def test_study_download_permissions_public(client_):
    study = StudyFactory.create(public=True)

    r = client_.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_",
    [
        lf("client"),
        lf("authenticated_client"),
        lf("staff_client"),
    ],
)
def test_study_task_detail_preview_permissions_public(client_):
    study = StudyFactory.create(public=True)
    # TODO: Due to the implementation of studies, a StudyTask necessary for images to be known
    StudyTaskFactory.create(study=study)

    r = client_.get(reverse("study-task-detail-preview", args=[study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 403),
        (lf("staff_client"), 200),
    ],
)
def test_study_task_detail_preview_permissions_private(client_, status):
    study = StudyFactory.create(public=False)
    # TODO: Due to the implementation of studies, a StudyTask necessary for images to be known
    StudyTaskFactory.create(study=study)

    r = client_.get(reverse("study-task-detail-preview", args=[study.pk]))
    assert r.status_code == status


@pytest.mark.django_db
def test_study_task_detail_preview_permissions_private_owner(client):
    study = StudyFactory.create(public=False)
    # TODO: Due to the implementation of studies, a StudyTask necessary for images to be known
    StudyTaskFactory.create(study=study)

    assert study.owners.exists()
    for owner in study.owners.all():
        client.force_login(owner)
        r = client.get(reverse("study-task-detail-preview", args=[study.pk]))
        assert r.status_code == 200


@pytest.mark.django_db
def test_study_task_detail_preview_permissions_private_annotator(client):
    study = StudyFactory.create(public=False)
    user = UserFactory.create()
    # TODO: Due to the implementation of studies, a StudyTask necessary for images to be known
    StudyTaskFactory.create(study=study, annotator=user)

    client.force_login(user)
    r = client.get(reverse("study-task-detail-preview", args=[study.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 403),
        (lf("staff_client"), 200),
    ],
)
def test_study_task_detail_invisible_to_non_annotators(client_, status):
    study_task = StudyTaskFactory.create()

    r = client_.get(reverse("study-task-detail", args=[study_task.pk]))
    assert r.status_code == status


@pytest.mark.django_db
def test_study_task_detail_visible_to_annotator(client):
    study_task = StudyTaskFactory.create()
    client.force_login(study_task.annotator)

    r = client.get(reverse("study-task-detail", args=[study_task.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_task_detail_visible_to_study_owner(client):
    study_task = StudyTaskFactory.create()
    client.force_login(study_task.study.creator)

    r = client.get(reverse("study-task-detail", args=[study_task.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_task_detail_shows_private_images_to_annotator():
    # This test is more about documenting a policy decision which allows a user to see
    # an image via a study task, but not directly.
    # This allows a person to conduct a study on images they haven't explicitly shared.
    image = ImageFactory.create(public=False)
    study_task = StudyTaskFactory.create(image=image)

    assert not study_task.annotator.has_perm("core.view_image", image)
    assert study_task.annotator.has_perm("studies.view_study_task", study_task)


@pytest.mark.skip("Migrating model so test is temporarily broken")
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 302),
        (lf("staff_client"), 200),
    ],
)
def test_study_view_mask_permissions(client_, status):
    markup = MarkupFactory.create()

    r = client_.get(reverse("view-mask", args=[markup.pk]))
    assert r.status_code == status


@pytest.mark.skip("Migrating model so test is temporarily broken")
@pytest.mark.django_db
def test_study_view_mask_permissions_annotator(client):
    markup = MarkupFactory.create()

    # TODO: markup creators can't see their own masks
    client.force_login(markup.annotation.annotator)
    r = client.get(reverse("view-mask", args=[markup.pk]))
    assert r.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 302),  # TODO: Should be 404
        (lf("staff_client"), 200),
    ],
)
def test_annotation_detail_permissions(client_, status):
    annotation = AnnotationFactory.create()

    r = client_.get(reverse("annotation-detail", args=[annotation.pk]))
    assert r.status_code == status


@pytest.mark.django_db
def test_annotation_detail_permissions_annotator(client):
    annotation = AnnotationFactory.create()

    # TODO: annotation creators can't see their own annotations
    client.force_login(annotation.annotator)
    r = client.get(reverse("annotation-detail", args=[annotation.pk]))
    assert r.status_code == 302  # TODO: Should be 404


@pytest.mark.django_db
def test_study_task_detail_post(client):
    question = QuestionFactory.create()
    study = StudyFactory.create(
        questions=[question],
        questions__required=True,
    )

    study_task = StudyTaskFactory.create(study=study)
    user = study_task.annotator
    client.force_login(user)
    choice = question.choices.first()
    client.post(
        reverse("study-task-detail", args=[study_task.pk]),
        {"start_time": timezone.now(), question.pk: choice.pk},
    )
    assert study_task.annotation

    response = study_task.annotation.responses.first()
    assert response.annotation.annotator == user
    assert response.question == question
    assert response.choice == choice
