class Echo:
    """
    A file-like object which returns written values instead of storing them.

    csv.writer.writerow returns whatever the underlying write() returns (rather than the
    int that a real file would return), allowing rows to be yielded to a
    StreamingHttpResponse as they're written. See
    https://docs.djangoproject.com/en/stable/howto/outputting-csv/#streaming-large-csv-files
    """

    def write(self, value: str) -> bytes:
        return value.encode("utf-8")
