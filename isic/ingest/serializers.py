from rest_framework import serializers

from isic.ingest.models import Accession


class AccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = [
            'id',
            'status',
            'quality_check',
            'diagnosis_check',
            'phi_check',
            'duplicate_check',
            'lesion_check',
        ]
