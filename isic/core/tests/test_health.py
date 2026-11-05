import pytest

from isic.core.health import (
    check_engagement_profile_defaults_consistent,
    check_iptc_metadata_consistency,
    run_all_health_checks,
)
from isic.core.services.iptc import embed_iptc_metadata_for_image


@pytest.mark.django_db
def test_health_checks_run():
    # this is just a smoke test to verify these run in their default state
    run_all_health_checks()


@pytest.mark.django_db
def test_engagement_profile_defaults_inconsistent(
    engagement_profile_factory, cohort_factory, contributor_factory
):
    engagement_profile_factory(
        default_contributor=contributor_factory(), default_cohort=cohort_factory()
    )

    result = check_engagement_profile_defaults_consistent()
    assert not result.passed
    assert "1 engagement profiles" in result.message


@pytest.mark.django_db
def test_iptc_metadata_consistency(image_factory):
    embedded_image = image_factory(public=False)
    embed_iptc_metadata_for_image(embedded_image)

    result = check_iptc_metadata_consistency()
    assert result.passed, result.message

    unembedded_image = image_factory(public=False)

    result = check_iptc_metadata_consistency()
    assert not result.passed
    assert embedded_image.isic_id not in result.message
    assert f"{unembedded_image.isic_id} blob: Iptc.Application2.Credit" in result.message
    assert f"{unembedded_image.isic_id} thumbnail: Iptc.Application2.Credit" in result.message

    embed_iptc_metadata_for_image(unembedded_image)
    original_attribution = unembedded_image.accession.attribution
    unembedded_image.accession.attribution = f"{original_attribution} changed"
    unembedded_image.accession.save(update_fields=["attribution"])

    result = check_iptc_metadata_consistency()
    assert not result.passed
    mismatch = (
        f"Iptc.Application2.Credit expected={original_attribution + ' changed'!r} "
        f"actual={original_attribution!r}"
    )
    assert result.message == (
        f"Found issues: {unembedded_image.isic_id} blob: {mismatch}; "
        f"{unembedded_image.isic_id} thumbnail: {mismatch}"
    )
