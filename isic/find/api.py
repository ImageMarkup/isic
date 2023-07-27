from django.http.response import JsonResponse
from ninja import Query, Router, Schema
from pydantic import validator

from isic.find.find import quickfind_execute

router = Router()


class QueryIn(Schema):
    query: str

    @validator("query")
    @classmethod
    def query_min_length(cls, v: str):
        if len(v) < 3:
            raise ValueError("Query too short.")
        return v

    @validator("query")
    @classmethod
    def query_too_common(cls, v: str):
        if v.lower() in "isic_":
            # Every image starts with ISIC_, so this would produce
            # far too many results to be meaningful. Force the user
            # to enter more information.
            raise ValueError("Query too common.")
        return v


@router.get("/", include_in_schema=False)
def quickfind(request, payload: QueryIn = Query(...)):  # noqa: B008
    return JsonResponse(quickfind_execute(payload.query, request.user), safe=False)
