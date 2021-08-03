from rest_framework import serializers

from isic.core.models import Image


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
            obj.accession.metadata['age_approx'] = int(
                round(obj.accession.metadata['age'] / 5.0) * 5
            )
            del obj.accession.metadata['age']
        return obj.accession.metadata
