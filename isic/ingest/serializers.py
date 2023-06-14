from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from isic.ingest.models import MetadataFile
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            "id",
            "created",
            "creator",
            "contributor",
            "name",
            "description",
            "copyright_license",
            "attribution",
            "accession_count",
        ]
        read_only_fields = ["created", "creator", "accession_count"]

    accession_count = serializers.SerializerMethodField()

    def get_accession_count(self, obj):
        return obj.accession_count

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user
        return super().create(validated_data)

    # TODO: figure out how to better integrate this into the permissions system
    def validate_contributor(self, value):
        if not self.context["request"].user.has_perm("ingest.add_cohort", value):
            raise PermissionDenied
        return value

    def validate(self, data):
        """
        Check that the user is a contributor owner.

        Note: this isn't quite the same as checking permissions because a superuser
        shouldn't be able to create a cohort with a non-contributor owner as the creator.
        """
        if not data["contributor"].owners.contains(self.context["request"].user):
            raise ValidationError("Cohort creator is not a contributor owner.")

        return data


class ContributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = [
            "id",
            "created",
            "creator",
            "owners",
            "institution_name",
            "institution_url",
            "legal_contact_info",
            "default_copyright_license",
            "default_attribution",
        ]
        read_only_fields = ["created", "creator", "owners"]

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user
        validated_data["owners"] = [self.context["request"].user]
        return super().create(validated_data)


class MetadataFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetadataFile
        fields = [
            "id",
        ]
