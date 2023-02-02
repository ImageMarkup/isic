from functools import partial
from typing import Optional

from django.contrib.auth.models import AnonymousUser, User
from django.db.models.query_utils import Q
from jaro import jaro_winkler_metric

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.find.serializers import (
    CohortQuickfindResultSerializer,
    CollectionQuickfindResultSerializer,
    ContributorQuickfindResultSerializer,
    ImageQuickfindResultSerializer,
    StudyQuickfindResultSerializer,
    UserQuickfindResultSerializer,
)
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.studies.models import Study


def quickfind_execute(query: str, user: Optional[User] = None) -> list[dict]:
    if not user:
        user = AnonymousUser()

    searches = {
        "images": {
            "filter": Image.objects.select_related("accession__cohort")
            .prefetch_related("accession__cohort__contributor__owners")
            .filter(isic__id__icontains=query)
            .order_by(),  # avoid ordering by created so index gets used
            "sort": "isic_id",
            "permission": "core.view_image",
            "serializer": ImageQuickfindResultSerializer,
        },
        "collections": {
            "filter": Collection.objects.select_related("creator").filter(name__icontains=query),
            "sort": "name",
            "permission": "core.view_collection",
            "serializer": CollectionQuickfindResultSerializer,
        },
        "studies": {
            "filter": Study.objects.filter(name__icontains=query),
            "sort": "name",
            "permission": "studies.view_study",
            "serializer": StudyQuickfindResultSerializer,
        },
        "cohorts": {
            "filter": Cohort.objects.filter(name__icontains=query),
            "sort": "name",
            "permission": "ingest.view_cohort",
            "serializer": CohortQuickfindResultSerializer,
        },
        "contributors": {
            "filter": Contributor.objects.filter(institution_name__icontains=query),
            "sort": "institution_name",
            "permission": "ingest.view_contributor",
            "serializer": ContributorQuickfindResultSerializer,
        },
        "users": {
            "filter": User.objects.filter(is_active=True)
            .filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(emailaddress__email__icontains=query)
            )
            .distinct(),
            "sort": lambda v: sum(
                jaro_winkler_metric(query.upper(), getattr(v, attr).upper())
                for attr in ["first_name", "last_name"]
            ),
            "permission": "",
            "serializer": UserQuickfindResultSerializer,
        },
    }

    ret = []

    def default_sort(search, v):
        return jaro_winkler_metric(query.upper(), getattr(v, search["sort"]).upper())

    for k, search in searches.items():
        if not user.is_staff:
            # Regular users can only search images/studies/collections.
            if k in ["cohorts", "users", "contributors"]:
                continue

        if search["permission"]:
            qs = get_visible_objects(user, search["permission"], search["filter"])
            items = list(qs)
        else:
            items = list(search["filter"])

        items = sorted(
            items,
            key=search["sort"] if callable(search["sort"]) else partial(default_sort, search),
            reverse=True,
        )[:5]

        for item in items:
            serializer = search["serializer"](item, context={"user": user})
            ret.append(serializer.data)

    return ret
