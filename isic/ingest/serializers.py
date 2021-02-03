from rest_framework import serializers

from isic.ingest.models import Accession


class AccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ['id', 'status', 'review_status', 'reject_reason']
