from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.core.models.collection import Collection
from isic.core.utils.csv import EscapingDictWriter

from .feature import Feature
from .question import Question
from .response import Response


class StudyQuerySet(models.QuerySet):
    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)


class Study(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        verbose_name_plural = "Studies"

    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    owners = models.ManyToManyField(User, related_name="owned_studies")
    attribution = models.CharField(max_length=200)

    name = models.CharField(max_length=100, unique=True, help_text="The name for your Study.")
    description = models.TextField(
        help_text="A description of the methodology behind your Study.", blank=True
    )

    # TODO: refactor code to get images from here instead of inspecting study tasks
    collection = models.ForeignKey(
        Collection,
        on_delete=models.PROTECT,
        related_name="studies",
        help_text="The Collection of images to use in your Study.",
    )

    features = models.ManyToManyField(Feature)
    questions = models.ManyToManyField(Question, through="StudyQuestion")

    # public study means that all images in the study must be public
    # and all of the related data to the study is public (responses).
    # if a study is private, only the owners can see the responses of
    # a study.
    # TODO: implement public checking
    public = models.BooleanField(
        default=False,
        help_text=(
            "Whether or not your Study will be public. A study can only be public if "
            "the images it uses are also public."
        ),
    )

    objects = StudyQuerySet.as_manager()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("study-detail", args=[self.pk])

    def write_responses_csv(self, stream) -> None:
        fieldnames = ["image", "annotator", "annotation_duration", "question", "answer"]
        writer = EscapingDictWriter(stream, fieldnames)

        writer.writeheader()

        for response in Response.objects.filter(annotation__study=self).for_display():
            writer.writerow({field: response[field] for field in fieldnames})

    def clean(self):
        if self.public and not self.collection.public:
            raise ValidationError("Can't make a study public with a private collection.")

        if self.collection.is_magic:
            raise ValidationError("Can't make a study from a magic collection.")


class StudyPermissions:
    model = Study
    perms = ["view_study", "view_study_results", "edit_study"]
    filters = {
        "view_study": "view_study_list",
        "view_study_results": "view_study_results_list",
        "edit_study": "edit_study_list",
    }

    @staticmethod
    def view_study_results_list(
        user_obj: User, qs: QuerySet[Study] | None = None
    ) -> QuerySet[Study]:
        qs = qs if qs is not None else Study.objects.all()

        # There's duplication of this check in study_detail.html
        if user_obj.is_staff:
            return qs

        if user_obj.is_authenticated:
            return qs.filter(Q(owners=user_obj) | Q(public=True))

        return qs.public()

    @staticmethod
    def view_study_results(user_obj, obj):
        return StudyPermissions.view_study_results_list(user_obj).contains(obj)

    @staticmethod
    def view_study_list(user_obj: User, qs: QuerySet[Study] | None = None) -> QuerySet[Study]:
        qs = qs if qs is not None else Study.objects.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            # Owner of the study, it's public, or the user has been assigned a task from
            # the study.
            return qs.filter(
                Q(creator=user_obj)
                | Q(owners=user_obj)
                | Q(public=True)
                | Q(tasks__annotator=user_obj)
            )

        return qs.public()

    @staticmethod
    def edit_study_list(user_obj: User, qs: QuerySet[Study] | None = None) -> QuerySet[Study]:
        qs = qs if qs is not None else Study.objects.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            return qs.filter(Q(creator=user_obj) | Q(owners=user_obj))

        return qs.none()

    @staticmethod
    def edit_study(user_obj, obj):
        return StudyPermissions.edit_study_list(user_obj).contains(obj)

    @staticmethod
    def view_study(user_obj, obj):
        return StudyPermissions.view_study_list(user_obj).contains(obj)


Study.perms_class = StudyPermissions
