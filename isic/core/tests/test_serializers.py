import pytest
from rest_framework import serializers

from isic.core.serializers import CollectionsField


class DummySerializer(serializers.Serializer):
    test = CollectionsField()


@pytest.mark.parametrize("input", [123, "abc", True])
def test_collections_field_invalid_inputs(input):
    s = DummySerializer(data={"test": input})
    with pytest.raises(serializers.ValidationError):
        s.is_valid(raise_exception=True)


@pytest.mark.parametrize(
    "input,output",
    [
        ["1,2,3", [1, 2, 3]],
        ["1", [1]],
    ],
)
def test_collections_field_valid_inputs(input, output):
    s = DummySerializer(data={"test": input})
    s.is_valid(raise_exception=True)
    assert s.validated_data.get("test") == output
