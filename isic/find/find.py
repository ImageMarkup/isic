from functools import partial
import heapq

from django.contrib.auth.models import User
from django.db.models.query_utils import Q
from jaro import jaro_winkler_metric

from isic.core.models.collection import Collection
from isic.core.models.doi import Doi
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.find.serializers import (
    CohortQuickfindResultSerializer,
    CollectionQuickfindResultSerializer,
    ContributorQuickfindResultSerializer,
    DoiQuickfindResultSerializer,
    ImageQuickfindResultSerializer,
    StudyQuickfindResultSerializer,
    UserQuickfindResultSerializer,
)
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.studies.models import Study


def _closest_images(query: str, user: User) -> list[Image]:
    # a short query can match every image, so only the ids are ranked, and only the closest
    # images are loaded.
    isic_ids = (
        get_visible_objects(
            user,
            "core.view_image",
            # avoid ordering by created so index gets used
            Image.objects.filter(isic__id__icontains=query).order_by(),
        )
        .values_list("isic_id", flat=True)
        .iterator()
    )
    closest = heapq.nlargest(
        5, isic_ids, key=lambda isic_id: jaro_winkler_metric(query.upper(), isic_id.upper())
    )
    images = (
        Image.objects.select_related("accession__cohort")
        .prefetch_related("accession__cohort__contributor__owners")
        .in_bulk(closest, field_name="isic_id")
    )
    return [images[isic_id] for isic_id in closest]


def quickfind_execute(query: str, user: User) -> list[dict]:
    searches = {
        "collections": {
            "filter": Collection.objects.select_related("creator").filter(name__icontains=query),
            "sort": "name",
            "permission": "core.view_collection",
            "serializer": CollectionQuickfindResultSerializer,
        },
        "studies": {
            "filter": Study.objects.select_related("creator").filter(name__icontains=query),
            "sort": "name",
            "permission": "studies.view_study",
            "serializer": StudyQuickfindResultSerializer,
        },
        "cohorts": {
            "filter": Cohort.objects.select_related("creator").filter(name__icontains=query),
            "sort": "name",
            "permission": "ingest.view_cohort",
            "serializer": CohortQuickfindResultSerializer,
        },
        "contributors": {
            "filter": Contributor.objects.select_related("creator").filter(
                institution_name__icontains=query
            ),
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
        "dois": {
            "filter": Doi.objects.select_related("collection", "creator").filter(
                collection__name__icontains=query
            ),
            "sort": lambda v: jaro_winkler_metric(query.upper(), v.collection.name.upper()),
            "permission": "",
            "serializer": DoiQuickfindResultSerializer,
        },
    }

    ret = ImageQuickfindResultSerializer(
        _closest_images(query, user), many=True, context={"user": user}
    ).data

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

        ret.extend(search["serializer"](items, many=True, context={"user": user}).data)

    return ret
