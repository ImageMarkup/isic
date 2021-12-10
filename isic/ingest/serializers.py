import os

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from isic.ingest.models import Accession, MetadataFile
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor


class AccessionSoftAcceptCheckSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    checks = serializers.ListField(child=serializers.CharField(), required=True)


class AccessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ['cohort', 'original_blob']

    def validate(self, data: dict) -> dict:
        data = super().validate(data)
        data['blob_name'] = os.path.basename(data['original_blob'])
        if data['cohort'].accessions.filter(blob_name=data['blob_name']).exists():
            raise ValidationError('An accession with this name already exists')

        return data


class AccessionChecksSerializer(serializers.ModelSerializer):
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


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            'id',
            'created',
            'creator',
            'contributor',
            'name',
            'description',
            'copyright_license',
            'attribution',
        ]
        read_only_fields = ['created', 'creator']

    def create(self, validated_data):
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)

    # TODO: figure out how to better integrate this into the permissions system
    def validate_contributor(self, value):
        if not self.context['request'].user.has_perm('ingest.add_cohort', value):
            raise PermissionDenied
        return value

    def validate(self, data):
        """
        Check that the user is a contributor owner.

        Note: this isn't quite the same as checking permissions because a superuser
        shouldn't be able to create a cohort with a non-contributor owner as the creator.
        """
        # TODO: use .contains in django 4
        if not data['contributor'].owners.filter(pk=self.context['request'].user.pk).exists():
            raise ValidationError('Cohort creator is not a contributor owner.')

        return data


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
