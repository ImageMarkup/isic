from abc import ABC, abstractmethod

from django.contrib.auth.models import User
from django.urls.base import reverse
from django.utils.text import capfirst
from ninja import Field, Schema

from isic.core.models import Collection, Image
from isic.core.models.doi import Doi
from isic.ingest.models import Cohort, Contributor
from isic.studies.models import Study


class QuickfindResultOut(Schema, ABC):
    title: str = Field(alias="name")
    subtitle: str
    icon: str
    url: str = Field(alias="get_absolute_url")
    yours: bool = False  # updated after creation
    result_type: str

    @staticmethod
    def resolve_subtitle(obj) -> str:
        return f"Created by {obj.creator.first_name} {obj.creator.last_name}"

    @staticmethod
    @abstractmethod
    def resolve_icon(obj) -> str: ...

    @staticmethod
    @abstractmethod
    def resolve_result_type(obj) -> str: ...

    def set_yours(self, obj, user: User) -> None:
        self.yours = obj.creator == user


class StudyQuickfindResultOut(QuickfindResultOut):
    @staticmethod
    def resolve_icon(_):
        return "ri-microscope-line"

    @staticmethod
    def resolve_result_type(_):
        return capfirst(Study._meta.verbose_name)


class ImageQuickfindResultOut(QuickfindResultOut):
    title: str = Field(alias="isic_id")

    @staticmethod
    def resolve_icon(_) -> str:
        return "ri-image-line"

    @staticmethod
    def resolve_result_type(_) -> str:
        return capfirst(Image._meta.verbose_name)

    @staticmethod
    def resolve_subtitle(obj: Image):
        return f"{obj.accession.attribution} ({obj.accession.copyright_license})"

    def set_yours(self, obj: Image, user: User) -> None:
        self.yours = user in obj.accession.cohort.contributor.owners.all()


class CollectionQuickfindResultOut(QuickfindResultOut):
    @staticmethod
    def resolve_subtitle(obj: Collection):
        return f"{obj.images.count()} images"

    @staticmethod
    def resolve_icon(_):
        return "ri-stack-line"

    @staticmethod
    def resolve_result_type(_):
        return capfirst(Collection._meta.verbose_name)


class CohortQuickfindResultOut(QuickfindResultOut):
    @staticmethod
    def resolve_subtitle(obj: Cohort):
        return obj.default_attribution

    @staticmethod
    def resolve_icon(_):
        return "ri-group-line"

    @staticmethod
    def resolve_result_type(_):
        return capfirst(Cohort._meta.verbose_name)


class ContributorQuickfindResultOut(QuickfindResultOut):
    title: str = Field(alias="institution_name")
    url: str

    @staticmethod
    def resolve_url(obj):
        return reverse("admin:ingest_contributor_change", args=[obj.pk])

    @staticmethod
    def resolve_subtitle(obj: Contributor):
        return ", ".join([f"{user.first_name} {user.last_name}" for user in obj.owners.all()])

    @staticmethod
    def resolve_icon(_):
        return "ri-government-line"

    @staticmethod
    def resolve_result_type(_):
        return capfirst(Contributor._meta.verbose_name)


class UserQuickfindResultOut(QuickfindResultOut):
    title: str
    url: str

    @staticmethod
    def resolve_url(obj):
        return reverse("core/user-detail", args=[obj.pk])

    @staticmethod
    def resolve_title(obj: User):
        return f"{obj.first_name} {obj.last_name}"

    @staticmethod
    def resolve_subtitle(obj):
        return obj.email

    @staticmethod
    def resolve_icon(_):
        return "ri-user-line"

    @staticmethod
    def resolve_result_type(_):
        return capfirst(str(User._meta.verbose_name))

    def set_yours(self, obj, user):
        self.yours = user == obj


class DoiQuickfindResultOut(QuickfindResultOut):
    title: str
    url: str

    @staticmethod
    def resolve_title(obj: Doi):
        return obj.collection.name

    @staticmethod
    def resolve_url(obj: Doi):
        return obj.get_absolute_url()

    @staticmethod
    def resolve_subtitle(obj: Doi):
        return f"DOI: {obj.id}"

    @staticmethod
    def resolve_icon(_):
        return "ri-file-text-line"

    @staticmethod
    def resolve_result_type(_):
        return Doi._meta.verbose_name

    def set_yours(self, obj: Doi, user: User) -> None:
        self.yours = obj.creator == user
