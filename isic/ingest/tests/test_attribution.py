from django.core.exceptions import ValidationError
import pytest

from isic.core.utils.csv import FORBIDDEN_LEADING_CHARS
from isic.ingest.services.cohort import create_cohort
from isic.ingest.services.contributor import create_contributor


@pytest.mark.django_db
def test_attribution_cannot_start_with_forbidden_leading_char(user, cohort, faker):
    for char in FORBIDDEN_LEADING_CHARS:
        attribution = f"{char}{faker.company()}"

        with pytest.raises(ValidationError, match="default_attribution"):
            create_contributor(
                creator=user,
                institution_name=faker.company(),
                legal_contact_info=faker.address(),
                default_attribution=attribution,
            )

        with pytest.raises(ValidationError, match="default_attribution"):
            create_cohort(
                creator=user,
                contributor=cohort.contributor,
                name=faker.sentence(),
                description=faker.paragraph(),
                default_copyright_license=cohort.default_copyright_license,
                default_attribution=attribution,
            )
