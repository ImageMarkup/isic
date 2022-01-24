import logging
import mimetypes
import shutil
import tempfile
from typing import IO

import magic

logger = logging.getLogger(__name__)


def guess_mime_type(content: IO[bytes], filename: str | None = None) -> str:
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
        shutil.copyfileobj(content, file_stream)
        file_stream.seek(0)

        # Calling .fileno() forces the file to be flushed to disk
        content_mime_type = m.from_descriptor(file_stream.fileno())
    content.seek(0)

    if filename is not None:
        filename_mime_type = mimetypes.guess_type(filename, strict=False)[0]
        if filename_mime_type is not None:
            # Right now, do not rely on `filename_mime_type` for the return value, but
            # warn if it's inconsistent with the content.
            if filename_mime_type != content_mime_type:
                logger.warning(
                    f'Inconsistent MIME types: content "{content_mime_type}", '
                    f'filename ({filename}) "{filename_mime_type}"'
                )

    return content_mime_type
