from base64 import b64decode, b64encode
from collections.abc import Sequence
from dataclasses import dataclass
from urllib import parse

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from rest_framework import serializers
from rest_framework.response import Response

# limit to protect against possibly malicious queries
_OFFSET_CUTOFF = 100


def qs_with_hardcoded_count(qs: QuerySet, ordering: Sequence, count: int) -> QuerySet:
    """
    Modify a queryset to return a hardcoded count rather than querying the database.

    This is useful when the count can be obtained with a cheaper method instead of
    the default queryset.count() method, e.g. elasticsearch, a separate query with
    fewer joins, etc.
    """
    # This is an unfortunate bit of hackery to get around the fact that the CursorPagination class
    # adds an order by which clones the queryset, overriding our hardcoded count. We have to repeat
    # the logic here to make sure the paginator doesn't modify our queryset.
    if not qs.query.order_by:
        qs = qs.order_by(*ordering)

    qs.count = lambda: count

    return qs


@dataclass
class Cursor:
    offset: int = 0
    reverse: bool = False
    position: str | None = None


def _clamp(val: int, min_: int, max_: int) -> int:
    return max(min_, min(val, max_))


def _reverse_order(order: Sequence[str]):
    """
    Reverse the ordering specification for a Django ORM query.

    Given an order_by tuple such as `('-created', 'uuid')` reverse the
    ordering and return a new tuple, eg. `('created', '-uuid')`.
    """

    def invert(x):
        return x[1:] if x.startswith("-") else f"-{x}"

    return tuple(invert(item) for item in order)


def _replace_query_param(url: str, key: str, val: str):
    scheme, netloc, path, query, fragment = parse.urlsplit(url)
    query_dict = parse.parse_qs(query, keep_blank_values=True)
    query_dict[key] = [val]
    query = parse.urlencode(sorted(query_dict.items()), doseq=True)
    return parse.urlunsplit((scheme, netloc, path, query, fragment))


class CursorPagination:
    default_ordering = ("-created",)
    max_page_size = 100

    def __init__(self, ordering: Sequence = default_ordering) -> None:
        self.ordering = ordering

    def paginate_queryset(
        self, queryset: QuerySet, request: HttpRequest, *, limit: int | None, cursor: Cursor
    ) -> dict:
        limit = _clamp(limit or self.max_page_size, 0, self.max_page_size)

        if not queryset.query.order_by:
            queryset = queryset.order_by(*self.ordering)

        order: tuple[str, ...] = queryset.query.order_by

        total_count = (
            # let the queryset define a custom_count attribute in the event that computing
            # the count can be done cheaper than the default queryset.count() method.
            queryset.custom_count
            if hasattr(queryset, "custom_count")
            else queryset.count()
            # only count the total number of results if a position is absent, usually indicating
            # that we're on the first page. this improves performance for larger queries.
            if cursor.position is None
            else None
        )

        base_url = request.build_absolute_uri()

        if cursor.reverse:
            queryset = queryset.order_by(*_reverse_order(order))

        queryset = self._apply_ordering(queryset, cursor, order)

        # If we have an offset cursor then offset the entire page by that amount.
        # We also always fetch an extra item in order to determine if there is a
        # page following on from this one.
        # Always fetch the maximum page size to increase cache utilization.
        results = list(queryset[cursor.offset : cursor.offset + self.max_page_size + 1])
        page = list(results[:limit])

        # Determine the position of the final item following the page.
        if len(results) > len(page):
            has_following_position = True
            following_position = self._get_position_from_instance(results[-1], order)
        else:
            has_following_position = False
            following_position = None

        if cursor.reverse:
            # If we have a reverse queryset, then the query ordering was in reverse
            # so we need to reverse the items again before returning them to the user.
            page.reverse()

            has_next = (cursor.position is not None) or (cursor.offset > 0)
            has_previous = has_following_position
            next_position = cursor.position if has_next else None
            previous_position = following_position if has_previous else None
        else:
            has_next = has_following_position
            has_previous = (cursor.position is not None) or (cursor.offset > 0)
            next_position = following_position if has_next else None
            previous_position = cursor.position if has_previous else None

        return {
            "results": page,
            "count": total_count,
            "next": (
                self.next_link(
                    base_url,
                    page,
                    cursor,
                    order,
                    has_previous,
                    limit,
                    next_position,
                    previous_position,
                )
                if has_next
                else None
            ),
            "previous": (
                self.previous_link(
                    base_url,
                    page,
                    cursor,
                    order,
                    has_next,
                    limit,
                    next_position,
                    previous_position,
                )
                if has_previous
                else None
            ),
        }

    def _encode_cursor(self, cursor: Cursor, base_url: str) -> str:
        tokens = {}
        if cursor.offset != 0:
            tokens["o"] = str(cursor.offset)
        if cursor.reverse:
            tokens["r"] = "1"
        if cursor.position is not None:
            tokens["p"] = cursor.position

        querystring = parse.urlencode(tokens, doseq=True)
        encoded = b64encode(querystring.encode()).decode()
        return _replace_query_param(base_url, "cursor", encoded)

    def next_link(  # noqa: PLR0913
        self,
        base_url: str,
        page: list,
        cursor: Cursor,
        order: Sequence[str],
        has_previous: bool,
        limit: int,
        next_position: str | None,
        previous_position: str | None,
    ) -> str:
        if page and cursor.reverse and cursor.offset:
            # If we're reversing direction and we have an offset cursor
            # then we cannot use the first position we find as a marker.
            compare = self._get_position_from_instance(page[-1], order)
        else:
            compare = next_position
        offset = 0

        has_item_with_unique_position = False
        for item in reversed(page):
            position = self._get_position_from_instance(item, order)
            if position != compare:
                # The item in this position and the item following it
                # have different positions. We can use this position as
                # our marker.
                has_item_with_unique_position = True
                break

            # The item in this position has the same position as the item
            # following it, we can't use it as a marker position, so increment
            # the offset and keep seeking to the previous item.
            compare = position
            offset += 1  # noqa: SIM113

        if page and not has_item_with_unique_position:
            # There were no unique positions in the page.
            if not has_previous:
                # We are on the first page.
                # Our cursor will have an offset equal to the page size,
                # but no position to filter against yet.
                offset = limit
                position = None
            elif cursor.reverse:
                # The change in direction will introduce a paging artifact,
                # where we end up skipping forward a few extra items.
                offset = 0
                position = previous_position
            else:
                # Use the position from the existing cursor and increment
                # it's offset by the page size.
                offset = cursor.offset + limit
                position = previous_position

        if not page:
            position = next_position

        next_cursor = Cursor(offset=offset, reverse=False, position=position)
        return self._encode_cursor(next_cursor, base_url)

    def previous_link(  # noqa: PLR0913
        self,
        base_url: str,
        page: list,
        cursor: Cursor,
        order: Sequence[str],
        has_next: bool,
        limit: int,
        next_position: str | None,
        previous_position: str | None,
    ) -> str:
        if page and not cursor.reverse and cursor.offset:
            # If we're reversing direction and we have an offset cursor
            # then we cannot use the first position we find as a marker.
            compare = self._get_position_from_instance(page[0], order)
        else:
            compare = previous_position
        offset = 0

        has_item_with_unique_position = False
        for item in page:
            position = self._get_position_from_instance(item, order)
            if position != compare:
                # The item in this position and the item following it
                # have different positions. We can use this position as
                # our marker.
                has_item_with_unique_position = True
                break

            # The item in this position has the same position as the item
            # following it, we can't use it as a marker position, so increment
            # the offset and keep seeking to the previous item.
            compare = position
            offset += 1  # noqa: SIM113

        if page and not has_item_with_unique_position:
            # There were no unique positions in the page.
            if not has_next:
                # We are on the final page.
                # Our cursor will have an offset equal to the page size,
                # but no position to filter against yet.
                offset = limit
                position = None
            elif cursor.reverse:
                # Use the position from the existing cursor and increment
                # it's offset by the page size.
                offset = cursor.offset + limit
                position = next_position
            else:
                # The change in direction will introduce a paging artifact,
                # where we end up skipping back a few extra items.
                offset = 0
                position = next_position

        if not page:
            position = previous_position

        cursor = Cursor(offset=offset, reverse=True, position=position)
        return self._encode_cursor(cursor, base_url)

    def _apply_ordering(self, queryset, cursor, order):
        if cursor.position is not None:
            is_reversed = order[0].startswith("-")
            order_attr = order[0].lstrip("-")

            # The cursor "position" is user-controlled, so part of validation is ensuring it's
            # parseable as the type of the ordering field (e.g. it's not a mangled datetime string).
            try:
                position = queryset.model._meta.get_field(order_attr).to_python(cursor.position)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"cursor": ["Invalid cursor."]}) from e

            if cursor.reverse != is_reversed:
                queryset = queryset.filter(**{f"{order_attr}__lt": position})
            else:
                queryset = queryset.filter(**{f"{order_attr}__gt": position})
        return queryset

    def _get_position_from_instance(self, instance, ordering):
        field_name = ordering[0].lstrip("-")
        attr = instance[field_name] if isinstance(instance, dict) else getattr(instance, field_name)
        return str(attr)


class CursorPaginationSerializer(serializers.Serializer):
    limit = serializers.IntegerField(allow_null=True, default=None)
    cursor = serializers.CharField(allow_null=True, default=None, trim_whitespace=False)

    def validate_cursor(self, encoded_cursor: str | None) -> Cursor:
        if encoded_cursor is None:
            return Cursor()

        try:
            querystring = b64decode(encoded_cursor).decode()
            tokens = parse.parse_qs(querystring, keep_blank_values=True)

            offset = int(tokens.get("o", ["0"])[0])
            offset = _clamp(offset, 0, _OFFSET_CUTOFF)

            reverse_str = tokens.get("r", ["0"])[0]
            reverse = bool(int(reverse_str))

            position = tokens.get("p", [None])[0]
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError("Invalid cursor.") from e

        return Cursor(offset=offset, reverse=reverse, position=position)


def paginate(request, queryset: QuerySet, serializer_class, paginator=None) -> Response:
    paginator = paginator if paginator is not None else CursorPagination()
    params = CursorPaginationSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    page = paginator.paginate_queryset(queryset, request, **params.validated_data)
    return Response({**page, "results": serializer_class(page["results"], many=True).data})
