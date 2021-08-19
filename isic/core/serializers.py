from rest_framework import serializers

from isic.core.models import Image
from isic.core.models.image import RESTRICTED_SEARCH_FIELDS


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
        obj.accession.metadata['age_approx'] = obj.accession.age_approx

        for field in RESTRICTED_SEARCH_FIELDS:
            if field in obj.accession.metadata:
                del obj.accession.metadata[field]

        return obj.accession.metadata
