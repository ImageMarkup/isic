from rest_framework import serializers

from isic.ingest.models import Accession, MetadataFile
from isic.ingest.models.contributor import Contributor


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


class ContributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = [
            'id',
            'created',
            'creator',
            'owners',
            'institution_name',
            'institution_url',
            'legal_contact_info',
            'default_copyright_license',
            'default_attribution',
        ]
        read_only_fields = ['created', 'creator', 'owners']

    def create(self, validated_data):
        validated_data['creator'] = self.context['request'].user
        validated_data['owners'] = [self.context['request'].user]
        return super().create(validated_data)


class MetadataFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetadataFile
        fields = [
            'id',
        ]
