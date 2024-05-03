from dataclasses import dataclass
import logging
import mimetypes
import shutil
import tempfile
from typing import IO

from magic import Magic

logger = logging.getLogger(__name__)


@dataclass
class MimeType:
    major: str
    minor: str

    def __init__(self, mime_type: str) -> None:
        self.major, _, self.minor = mime_type.partition("/")

    def __str__(self) -> str:
        return f"{self.major}/{self.minor}"


def guess_mime_type(content: IO[bytes], source_filename: str | None = None) -> MimeType:
    """
    Guess the MIME type of a file, based on its content.

    An optional `filename` can be provided, to provide extra context for guessing.
    """
    magic = Magic(mime=True)

    # This initial seek is just defensive
    content.seek(0)
    with tempfile.TemporaryFile() as file_stream:
        # Copy blob_stream into a TemporaryFile so it can be used by magic,
        # which does not accept a file-like object
        shutil.copyfileobj(content, file_stream)
        file_stream.seek(0)

        content_mime_type = MimeType(magic.from_descriptor(file_stream.fileno()))
    content.seek(0)

    if source_filename is not None:
        source_filename_mime_type = MimeType(
            mimetypes.guess_type(source_filename, strict=False)[0] or "application/octet-stream"
        )
        if source_filename_mime_type != content_mime_type:
            # Right now, do not rely on `source_filename_mime_type` for the return value, but
            # warn if it's inconsistent with the content.
            logger.warning(
                'Inconsistent MIME types: content is "%s", filename "%s" is "%s"',
                content_mime_type,
                source_filename,
                source_filename_mime_type,
            )

    return content_mime_type
