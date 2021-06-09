from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_study_list_permissions(client, authenticated_client, staff_client):
    r = client.get(reverse('study-list'))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('study-list'))
    assert r.status_code == 302

    r = staff_client.get(reverse('study-list'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_study_detail_permissions(study, client, authenticated_client, staff_client):
    r = client.get(reverse('study-detail', args=[study.pk]))
    assert r.status_code == 302

    # TODO: study creators can't see their own studies
    client.force_login(study.creator)
    r = client.get(reverse('study-detail', args=[study.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('study-detail', args=[study.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse('study-detail', args=[study.pk]))
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
