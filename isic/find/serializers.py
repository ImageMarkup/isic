from django.contrib.auth.models import User
from django.urls.base import reverse
from django.utils.text import capfirst
from rest_framework import serializers

from isic.core.models import Collection, Image
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.studies.models import Study


class QuickfindResultSerializer(serializers.Serializer):
    title = serializers.CharField(source="name")
    subtitle = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    url = serializers.URLField(source="get_absolute_url")
    yours = serializers.SerializerMethodField()
    result_type = serializers.SerializerMethodField()
    distance = serializers.FloatField(read_only=True)

    def get_subtitle(self, obj):
        return f"Created by {obj.creator.first_name} {obj.creator.last_name}"

    def get_icon(self, obj):
        raise NotImplementedError

    def get_yours(self, obj):
        return self.context["user"] == obj.creator

    def get_result_type(self, obj):
        raise NotImplementedError


class StudyQuickfindResultSerializer(QuickfindResultSerializer):
    def get_icon(self, obj):
        return "ri-microscope-line"

    def get_result_type(self, obj):
        return capfirst(Study._meta.verbose_name)


class ImageQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.CharField(source="isic_id")

    def get_subtitle(self, obj):
        return f"{obj.accession.cohort.attribution} ({obj.accession.copyright_license})"

    def get_icon(self, obj):
        return "ri-image-line"

    def get_yours(self, obj):
        return self.context["user"] in obj.accession.cohort.contributor.owners.all()

    def get_result_type(self, obj):
        return capfirst(Image._meta.verbose_name)


class CollectionQuickfindResultSerializer(QuickfindResultSerializer):
    def get_subtitle(self, obj):
        return f"{obj.images.count()} images"

    def get_icon(self, obj):
        return "ri-stack-line"

    def get_result_type(self, obj):
        return capfirst(Collection._meta.verbose_name)


class CohortQuickfindResultSerializer(QuickfindResultSerializer):
    def get_subtitle(self, obj):
        return obj.attribution

    def get_icon(self, obj):
        return "ri-group-line"

    def get_result_type(self, obj):
        return capfirst(Cohort._meta.verbose_name)


class ContributorQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.CharField(source="institution_name")
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return reverse("admin:ingest_contributor_change", args=[obj.pk])

    def get_subtitle(self, obj):
        return ", ".join([f"{user.first_name} {user.last_name}" for user in obj.owners.all()])

    def get_icon(self, obj):
        return "ri-government-line"

    def get_result_type(self, obj):
        return capfirst(Contributor._meta.verbose_name)


class UserQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return reverse("core/user-detail", args=[obj.pk])

    def get_title(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_subtitle(self, obj):
        return obj.email

    def get_icon(self, obj):
        return "ri-user-line"

    def get_yours(self, obj):
        return self.context["user"] == obj

    def get_result_type(self, obj):
        return capfirst(User._meta.verbose_name)
