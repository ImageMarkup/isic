from rest_framework import serializers

from isic.core.models import Image


class SearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


class ImageUrlSerializer(serializers.Serializer):
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
        if 'age' in obj.accession.metadata:
            obj.accession.metadata['age_approx'] = obj.accession.age_approx
            del obj.accession.metadata['age']

        return obj.accession.metadata
