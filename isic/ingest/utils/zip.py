from dataclasses import dataclass
import os
from typing import IO, Generator

import zipfile_deflate64 as zipfile


def _filtered_infolist(zip_file: zipfile.ZipFile) -> Generator[zipfile.ZipInfo, None, None]:
    """Filter a ZipFile infolist to only include actual files."""
    for file_info in zip_file.infolist():
        if file_info.is_dir() or not file_info.filename:
            # Skip likely directories
            continue
        if not file_info.file_size:
            # Skip empty files
            continue
        if _base_file_name(file_info.filename) in {'Thumbs.db', '.DS_Store'}:
            # Skip OS-generated files
            continue
        if _base_file_name(file_info.filename).startswith('._'):
            # File is probably a macOS resource fork, skip
            continue

        yield file_info


def _base_file_name(path: str) -> str:
    """Return the base name of a path."""
    return os.path.basename(path.replace('\\', '/'))


def file_names_in_zip(stream: IO[bytes]) -> Generator[str, None, None]:
    """Yield the base file names in a zip stream."""
    with zipfile.ZipFile(stream) as zip_file:
        for file_info in _filtered_infolist(zip_file):
            yield _base_file_name(file_info.filename)


@dataclass
class ZipItem:
    name: str
    stream: IO[bytes]
    size: int


def items_in_zip(stream: IO[bytes]) -> Generator[ZipItem, None, None]:
    """Yield the items in a zip stream."""
    with zipfile.ZipFile(stream) as zip_file:
        for file_info in _filtered_infolist(zip_file):
            with zip_file.open(file_info) as zip_file_stream:
                yield ZipItem(
                    name=_base_file_name(file_info.filename),
                    stream=zip_file_stream,
                    size=file_info.file_size,
                )
