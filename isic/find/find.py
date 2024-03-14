from functools import partial

from django.contrib.auth.models import User
from django.db.models.query_utils import Q
from jaro import jaro_winkler_metric

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.find.serializers import (
    CohortQuickfindResultOut,
    CollectionQuickfindResultOut,
    ContributorQuickfindResultOut,
    ImageQuickfindResultOut,
    StudyQuickfindResultOut,
    UserQuickfindResultOut,
)
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.studies.models import Study


def quickfind_execute(query: str, user: User) -> list[dict]:
    searches = {
        "images": {
            "filter": Image.objects.select_related("accession__cohort")
            .prefetch_related("accession__cohort__contributor__owners")
            .filter(isic__id__icontains=query)
            .order_by(),  # avoid ordering by created so index gets used
            "sort": "isic_id",
            "permission": "core.view_image",
            "serializer": ImageQuickfindResultOut,
        },
        "collections": {
            "filter": Collection.objects.select_related("creator").filter(name__icontains=query),
            "sort": "name",
            "permission": "core.view_collection",
            "serializer": CollectionQuickfindResultOut,
        },
        "studies": {
            "filter": Study.objects.filter(name__icontains=query),
            "sort": "name",
            "permission": "studies.view_study",
            "serializer": StudyQuickfindResultOut,
        },
        "cohorts": {
            "filter": Cohort.objects.filter(name__icontains=query),
            "sort": "name",
            "permission": "ingest.view_cohort",
            "serializer": CohortQuickfindResultOut,
        },
        "contributors": {
            "filter": Contributor.objects.filter(institution_name__icontains=query),
            "sort": "institution_name",
            "permission": "ingest.view_contributor",
            "serializer": ContributorQuickfindResultOut,
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
            "serializer": UserQuickfindResultOut,
        },
    }

    ret = []

    def default_sort(search, v):
        return jaro_winkler_metric(query.upper(), getattr(v, search["sort"]).upper())

    for k, search in searches.items():
        if not user.is_staff and k in ["cohorts", "users", "contributors"]:
            # Regular users can only search images/studies/collections.
            continue

        if search["permission"]:
            qs = get_visible_objects(user, search["permission"], search["filter"])
            items = list(qs)
        else:
            items = list(search["filter"])

        items = sorted(
            items,
            key=(search["sort"] if callable(search["sort"]) else partial(default_sort, search)),
            reverse=True,
        )[:5]

        for item in items:
            serializer = search["serializer"].from_orm(item)
            serializer.set_yours(item, user)
            ret.append(serializer.dict())

    return ret
