from django.contrib.auth.models import User
from django.urls.base import reverse
from django.utils.text import capfirst
from rest_framework import serializers

from isic.core.models import Collection, Image
from isic.core.models.doi import Doi
from isic.ingest.models import Cohort, Contributor
from isic.studies.models import Study


class QuickfindResultSerializer(serializers.Serializer):
    """
    Serialize one quickfind result.

    The user doing the search must be passed in the context as "user".
    """

    title = serializers.CharField(source="name")
    subtitle = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    url = serializers.CharField(source="get_absolute_url")
    yours = serializers.SerializerMethodField()
    result_type = serializers.SerializerMethodField()

    def get_subtitle(self, obj) -> str:
        return f"Created by {obj.creator.first_name} {obj.creator.last_name}"

    def get_yours(self, obj) -> bool:
        return obj.creator == self.context["user"]


class StudyQuickfindResultSerializer(QuickfindResultSerializer):
    def get_icon(self, _) -> str:
        return "ri-microscope-line"

    def get_result_type(self, _) -> str:
        return capfirst(Study._meta.verbose_name)


class ImageQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.CharField(source="isic_id")

    def get_icon(self, _) -> str:
        return "ri-image-line"

    def get_result_type(self, _) -> str:
        return capfirst(Image._meta.verbose_name)

    def get_subtitle(self, obj: Image) -> str:
        return f"{obj.accession.attribution} ({obj.accession.copyright_license})"

    def get_yours(self, obj: Image) -> bool:
        return self.context["user"] in obj.accession.cohort.contributor.owners.all()


class CollectionQuickfindResultSerializer(QuickfindResultSerializer):
    def get_subtitle(self, obj: Collection) -> str:
        return f"{obj.images.count()} images"

    def get_icon(self, _) -> str:
        return "ri-stack-line"

    def get_result_type(self, _) -> str:
        return capfirst(Collection._meta.verbose_name)


class CohortQuickfindResultSerializer(QuickfindResultSerializer):
    def get_subtitle(self, obj: Cohort) -> str:
        return obj.default_attribution

    def get_icon(self, _) -> str:
        return "ri-group-line"

    def get_result_type(self, _) -> str:
        return capfirst(Cohort._meta.verbose_name)


class ContributorQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.CharField(source="institution_name")
    url = serializers.SerializerMethodField()

    def get_url(self, obj: Contributor) -> str:
        return reverse("admin:ingest_contributor_change", args=[obj.pk])

    def get_subtitle(self, obj: Contributor) -> str:
        return ", ".join([f"{user.first_name} {user.last_name}" for user in obj.owners.all()])

    def get_icon(self, _) -> str:
        return "ri-government-line"

    def get_result_type(self, _) -> str:
        return capfirst(Contributor._meta.verbose_name)


class UserQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj: User) -> str:
        return reverse("core/user-detail", args=[obj.pk])

    def get_title(self, obj: User) -> str:
        return f"{obj.first_name} {obj.last_name}"

    def get_subtitle(self, obj: User) -> str:
        return obj.email

    def get_icon(self, _) -> str:
        return "ri-user-line"

    def get_result_type(self, _) -> str:
        return capfirst(str(User._meta.verbose_name))

    def get_yours(self, obj: User) -> bool:
        return self.context["user"] == obj


class DoiQuickfindResultSerializer(QuickfindResultSerializer):
    title = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_title(self, obj: Doi) -> str:
        return obj.collection.name

    def get_url(self, obj: Doi) -> str:
        return obj.get_absolute_url()

    def get_subtitle(self, obj: Doi) -> str:
        return f"DOI: {obj.id}"

    def get_icon(self, _) -> str:
        return "ri-file-text-line"

    def get_result_type(self, _) -> str:
        return str(Doi._meta.verbose_name)
