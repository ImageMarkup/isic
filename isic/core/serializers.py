from rest_framework import serializers

from isic.core.models import Image


class SearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False)


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            'public',
            'isic_id',
            'metadata',
        ]

    metadata = serializers.SerializerMethodField()

    def get_metadata(self, obj) -> dict:
        if 'age' in obj.accession.metadata:
            obj.accession.metadata['age_approx'] = obj.accession.age_approx
            del obj.accession.metadata['age']

        return obj.accession.metadata
