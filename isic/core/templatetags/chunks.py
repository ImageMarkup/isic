from django import template

register = template.Library()


def grouper(iterable, n):
    values = list(iterable)

    current = []
    for value in values:
        if len(current) == n:
            yield current
            current = [value]
        else:
            current.append(value)

    if current:
        yield current


@register.filter
def chunks(value, chunk_length):
    return grouper(value, chunk_length)
