import os
import shutil
import tempfile

import zipfile_deflate64 as zipfile


def files_in_zip(path):
    with zipfile.ZipFile(path) as zip_file:
        for original_file in zip_file.infolist():
            original_file_relpath = original_file.filename
            original_file_relpath.replace('\\', '/')
            original_filename = os.path.basename(original_file_relpath)
            # ignore likely directories
            if original_filename and original_file.file_size:
                yield original_file_relpath, original_filename


def unzip(path):
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(path) as zip_file:
            for filepath, filename in files_in_zip(path):
                temp_file_path = os.path.join(temp_dir, filename)
                with open(temp_file_path, 'wb') as temp_file_stream:
                    shutil.copyfileobj(zip_file.open(filepath), temp_file_stream)
                yield temp_file_path, filename
                os.remove(temp_file_path)
