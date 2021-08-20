from rest_framework import serializers

from isic.core.models import Image


class SearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            'isic_id',
            'public',
            'metadata',
            'thumbnail_url',
        ]

    metadata = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_thumbnail_url(self, obj) -> str:
        return obj.accession.thumbnail.url

    def get_metadata(self, obj) -> dict:
        if 'age' in obj.accession.metadata:
            obj.accession.metadata['age_approx'] = obj.accession.age_approx
            del obj.accession.metadata['age']

        return obj.accession.metadata
