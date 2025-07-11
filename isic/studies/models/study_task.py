from django.contrib.auth.models import User
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from isic.core.models import Image

from .study import Study


class StudyTaskSet(models.QuerySet):
    def pending(self):
        return self.filter(annotation=None)

    def for_user(self, user: User):
        return self.filter(annotator=user)

    def just_completed(self):
        return self.filter(
            annotation__created__gte=timezone.now() - timezone.timedelta(seconds=60)
        ).order_by("annotation__created")

    def random_next(self):
        # This is really inefficient when performing on large sets of rows,
        # and getting a set of rows in a random order is pretty hard in SQL.
        # This should always be called once the studytask queryset has been
        # narrowed a lot.
        return self.order_by("?").first()


class StudyTask(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        unique_together = [["study", "annotator", "image"]]

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="tasks")
    # TODO: annotators might become M2M in the future
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    objects = StudyTaskSet.as_manager()

    @property
    def complete(self) -> bool:
        return hasattr(self, "annotation")


class StudyTaskPermissions:
    model = StudyTask
    perms = ["view_study_task"]
    filters = {"view_study_task": "view_study_task_list"}

    @staticmethod
    def view_study_task_list(
        user_obj: User, qs: QuerySet[StudyTask] | None = None
    ) -> QuerySet[StudyTask]:
        qs = qs if qs is not None else StudyTask._default_manager.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            # Note: this allows people who can't see the image to see it if it's part of a study
            # task ONLY within the studytask check. In other words, they can't see it in the
            # gallery.
            return qs.filter(Q(annotator=user_obj) | Q(study__owners=user_obj))

        return qs.none()

    @staticmethod
    def view_study_task(user_obj, obj):
        return StudyTaskPermissions.view_study_task_list(user_obj).contains(obj)


StudyTask.perms_class = StudyTaskPermissions
