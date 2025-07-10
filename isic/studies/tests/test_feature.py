from django.core.exceptions import ValidationError
import pytest

from isic.studies.tests.factories import AnnotationFactory, FeatureFactory


@pytest.mark.django_db
def test_feature_modify_referenced() -> None:
    feature = FeatureFactory.create()

    AnnotationFactory.create(study__features=[feature])
    feature.name += " (modified)"

    with pytest.raises(ValidationError, match="it has already been marked up"):
        feature.save(update_fields=["name"])
