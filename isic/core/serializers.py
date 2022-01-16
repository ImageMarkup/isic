import re
from typing import Optional, Union

from django.contrib.auth.models import User
from pyparsing.exceptions import ParseException
from rest_framework import serializers
from rest_framework.fields import Field

from isic.core.dsl import parse_query
from isic.core.models import Image
from isic.core.models.collection import Collection


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'created', 'email', 'first_name', 'last_name', 'accepted_terms']

    created = serializers.DateTimeField(source='date_joined')
    accepted_terms = serializers.DateTimeField(source='profile.accepted_terms')


class CollectionsField(Field):
    """A field for comma separated collection ids."""

    default_error_messages = {
        'invalid': 'Not a valid string.',
        'not_comma_delimited': 'Not a comma delimited string.',
    }

    def to_representation(self, obj: list[int]) -> str:
        obj = super().to_representation(obj)
        return ','.join([str(element) for element in obj])

    def to_internal_value(self, data: Optional[Union[list, str]]) -> Optional[list[int]]:
        if data:
            # if the data is coming from swagger, it's built into a 1 element list
            if isinstance(data, list):
                data = data[0]
            elif not isinstance(data, str):
                self.fail('invalid')

            if not re.match(r'^(\d+)(,\d+)*$', data):
                self.fail('not_comma_delimited')

            data = [int(x) for x in data.split(',')]
            return data


def valid_search_query(value: str) -> None:
    # TODO: this means the DSL query gets parsed twice for /images/search
    try:
        parse_query(value)
    except ParseException:
        raise serializers.ValidationError('Invalid search query.')


class SearchQuerySerializer(serializers.Serializer):
    """A serializer for a search query against images."""

    query = serializers.CharField(
        required=False, help_text='A search query string.', validators=[valid_search_query]
    )
    collections = CollectionsField(
        required=False,
        help_text='A list of collection IDs to filter a query by, separated with a comma.',
    )


class ImageUrlSerializer(serializers.Serializer):
    full = serializers.URLField(source='accession.blob.url')
    thumbnail_256 = serializers.URLField(source='accession.thumbnail_256.url')


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            'isic_id',
            'public',
            'metadata',
            'urls',
        ]

    metadata = serializers.DictField(source='accession.redacted_metadata', read_only=True)
    urls = ImageUrlSerializer(source='*', read_only=True)


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = [
            'id',
            'name',
            'description',
            'public',
        ]
