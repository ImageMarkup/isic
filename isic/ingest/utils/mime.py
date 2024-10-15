import logging
import mimetypes
import shutil
import tempfile
from typing import IO

import magic

logger = logging.getLogger(__name__)


def guess_mime_type(content: IO[bytes], source_filename: str | None = None) -> str:
    """
    Guess the MIME type of a file, based on its content.

    An optional `filename` can be provided, to provide extra context for guessing.
    """
    m = magic.Magic(mime=True)

    # This initial seek is just defensive
    content.seek(0)
    with tempfile.SpooledTemporaryFile() as file_stream:
        # Copy blob_stream into a SpooledTemporaryFile so it can be used by magic,
        # which does not accept a file-like object
        shutil.copyfileobj(content, file_stream)  # type: ignore[misc]
        file_stream.seek(0)

        # Calling .fileno() forces the file to be flushed to disk
        content_mime_type = m.from_descriptor(file_stream.fileno())
    content.seek(0)

    if source_filename is not None:
        source_filename_mime_type = mimetypes.guess_type(source_filename, strict=False)[0]
        if source_filename_mime_type is not None and source_filename_mime_type != content_mime_type:
            # Right now, do not rely on `filename_mime_type` for the return value, but
            # warn if it's inconsistent with the content.
            logger.warning(
                'Inconsistent MIME types: content "%s", filename %s "%s"',
                content_mime_type,
                source_filename,
                source_filename_mime_type,
            )

    return content_mime_type
