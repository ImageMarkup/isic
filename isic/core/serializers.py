from rest_framework import serializers

from isic.core.models import Image
from isic.core.models.image import RESTRICTED_SEARCH_FIELDS


class SearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


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
