import re
from typing import Optional, Union

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.fields import Field

from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.models.image import RESTRICTED_SEARCH_FIELDS
from isic.core.permissions import get_visible_objects


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'created', 'email', 'first_name', 'last_name']

    created = serializers.DateTimeField(source='date_joined')


class CollectionsField(Field):
    """
    A field for comma separated collection ids.

    This field filters the collection ids to those that are visible
    to the user in context.
    """

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
            return self._filter_collection_pks(data)

    def _filter_collection_pks(self, collection_pks: list[int]) -> list[int]:
        visible_collection_pks = get_visible_objects(
            self.context['user'],
            'core.view_collection',
            Collection.objects.filter(pk__in=collection_pks),
        )

        return list(visible_collection_pks.values_list('pk', flat=True))


class SearchQuerySerializer(serializers.Serializer):
    """A serializer for a search query against images.

    Note that this serializer requires being called with a user object in
    the context.
    """

    query = serializers.CharField(
        required=False, help_text='A search query following the Elasticsearch query string syntax.'
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

    metadata = serializers.SerializerMethodField()
    urls = ImageUrlSerializer(source='*', read_only=True)

    def get_metadata(self, obj) -> dict:
        obj.accession.metadata['age_approx'] = obj.accession.age_approx

        for field in RESTRICTED_SEARCH_FIELDS:
            if field in obj.accession.metadata:
                del obj.accession.metadata[field]

        return obj.accession.metadata


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = [
            'id',
            'name',
            'description',
            'public',
        ]
