from django.db import IntegrityError
import pytest

from isic.core.models import SimilarImageFeedback


@pytest.mark.django_db
def test_similar_image_feedback_unauthenticated(client, image_factory):
    """Test that unauthenticated users cannot submit feedback."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    response = client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "up",
        },
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"
    assert SimilarImageFeedback.objects.count() == 0


@pytest.mark.django_db
def test_similar_image_feedback_thumbs_up(authenticated_client, user, image_factory):
    """Test that authenticated users can submit thumbs up feedback."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "up",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Feedback submitted successfully"
    assert response.json()["created"] is True
    assert response.json()["feedback"] == "up"

    # Verify feedback was saved
    feedback = SimilarImageFeedback.objects.get()
    assert feedback.image == source_image
    assert feedback.similar_image == similar_image
    assert feedback.user == user
    assert feedback.feedback == SimilarImageFeedback.THUMBS_UP


@pytest.mark.django_db
def test_similar_image_feedback_thumbs_down(authenticated_client, user, image_factory):
    """Test that authenticated users can submit thumbs down feedback."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "down",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Feedback submitted successfully"
    assert response.json()["created"] is True
    assert response.json()["feedback"] == "down"

    # Verify feedback was saved
    feedback = SimilarImageFeedback.objects.get()
    assert feedback.image == source_image
    assert feedback.similar_image == similar_image
    assert feedback.user == user
    assert feedback.feedback == SimilarImageFeedback.THUMBS_DOWN


@pytest.mark.django_db
def test_similar_image_feedback_update(authenticated_client, user, image_factory):
    """Test that submitting feedback again updates the existing record."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    # Submit initial thumbs up
    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "up",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["created"] is True
    assert SimilarImageFeedback.objects.count() == 1

    # Update to thumbs down
    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "down",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["feedback"] == "down"

    # Verify only one feedback record exists and it's updated
    assert SimilarImageFeedback.objects.count() == 1
    feedback = SimilarImageFeedback.objects.get()
    assert feedback.feedback == SimilarImageFeedback.THUMBS_DOWN


@pytest.mark.django_db
def test_similar_image_feedback_invalid_value(authenticated_client, image_factory):
    """Test that invalid feedback values are rejected."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": similar_image.isic_id,
            "feedback": "invalid",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Invalid feedback value"
    assert SimilarImageFeedback.objects.count() == 0


@pytest.mark.django_db
def test_similar_image_feedback_nonexistent_image(authenticated_client, image_factory):
    """Test that feedback for nonexistent images returns 404."""
    source_image = image_factory(public=True)

    response = authenticated_client.post(
        f"/api/v2/images/{source_image.isic_id}/similar-feedback/",
        data={
            "similar_image_id": "ISIC_9999999",
            "feedback": "up",
        },
        content_type="application/json",
    )

    assert response.status_code == 404
    assert SimilarImageFeedback.objects.count() == 0


@pytest.mark.django_db
def test_similar_image_feedback_source_image_not_found(authenticated_client):
    """Test that feedback for nonexistent source image returns 404."""
    response = authenticated_client.post(
        "/api/v2/images/ISIC_9999999/similar-feedback/",
        data={
            "similar_image_id": "ISIC_9999998",
            "feedback": "up",
        },
        content_type="application/json",
    )

    assert response.status_code == 404
    assert SimilarImageFeedback.objects.count() == 0


@pytest.mark.django_db
def test_similar_image_feedback_unique_constraint(user, image_factory):
    """Test that the unique constraint on image, similar_image, and user works."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    # Create first feedback
    SimilarImageFeedback.objects.create(
        image=source_image,
        similar_image=similar_image,
        user=user,
        feedback=SimilarImageFeedback.THUMBS_UP,
    )

    # Trying to create another feedback with same combination should work
    # because update_or_create handles it, but direct create should fail
    with pytest.raises(IntegrityError):
        SimilarImageFeedback.objects.create(
            image=source_image,
            similar_image=similar_image,
            user=user,
            feedback=SimilarImageFeedback.THUMBS_DOWN,
        )


@pytest.mark.django_db
def test_similar_image_feedback_model_str(user, image_factory):
    """Test the string representation of the feedback model."""
    source_image = image_factory(public=True)
    similar_image = image_factory(public=True)

    feedback = SimilarImageFeedback.objects.create(
        image=source_image,
        similar_image=similar_image,
        user=user,
        feedback=SimilarImageFeedback.THUMBS_UP,
    )

    expected = f"{user.username}: {source_image.isic_id} -> {similar_image.isic_id} (up)"
    assert str(feedback) == expected
