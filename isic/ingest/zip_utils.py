import os
import shutil
import subprocess
import sys
import tempfile
import zipfile


class TempDir(object):
    def __init__(self):
        pass

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        return self.temp_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(self.temp_dir)


class ZipFileOpener(object):
    def __init__(self, zip_file_path):
        self.zip_file_path = zip_file_path
        # TODO: check for "7z" command

    def __enter__(self):
        # Create temporary directory
        self.temp_dir_manager = TempDir()
        self.temp_dir = self.temp_dir_manager.__enter__()

        try:
            return self._default_unzip()
        except (zipfile.BadZipfile, NotImplementedError):
            return self._fallback_unzip()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Destroy temporary directory
        self.temp_dir_manager.__exit__(exc_type, exc_val, exc_tb)

    def _default_unzip(self):
        zip_file = zipfile.ZipFile(self.zip_file_path)

        # filter out directories and count real files
        file_list = []
        for original_file in zip_file.infolist():
            original_file_relpath = original_file.filename
            original_file_relpath.replace('\\', '/')
            original_file_name = os.path.basename(original_file_relpath)
            if not original_file_name or not original_file.file_size:
                # file is probably a directory, skip
                continue
            if original_file_name.startswith('._'):
                # file is probably a macOS resource fork, skip
                continue
            file_list.append((original_file, original_file_relpath))
        # Test whether the archive uses a compression type that the zip_file module supports. For
        # example, extracting from an archive that uses Deflate64 raises the following exception:
        # "NotImplementedError: compression type 9 (deflate64)"
        if file_list:
            with zip_file.open(file_list[0][0]):
                pass

        return self._default_unzip_iter(zip_file, file_list), len(file_list)

    def _default_unzip_iter(self, zip_file, file_list):
        for original_file, original_file_relpath in file_list:
            original_file_name = os.path.basename(original_file_relpath)
            temp_file_path = os.path.join(self.temp_dir, original_file_name)
            with open(temp_file_path, 'wb') as temp_file_stream:
                shutil.copyfileobj(zip_file.open(original_file), temp_file_stream)
            yield temp_file_path, original_file_relpath
            os.remove(temp_file_path)
        zip_file.close()

    def _fallback_unzip(self):
        unzip_command = ('7z', 'x', '-y', f'-o{self.temp_dir}', self.zip_file_path)
        try:
            with open(os.devnull, 'rb') as null_in, open(os.devnull, 'wb') as null_out:
                subprocess.check_call(
                    unzip_command, stdin=null_in, stdout=null_out, stderr=subprocess.STDOUT
                )
        except subprocess.CalledProcessError:
            self.__exit__(*sys.exc_info())
            raise

        file_list = []
        for temp_dir_path, _, temp_file_names in os.walk(self.temp_dir):
            for temp_file_name in temp_file_names:
                temp_file_path = os.path.join(temp_dir_path, temp_file_name)
                original_file_relpath = os.path.relpath(temp_file_path, self.temp_dir)
                if temp_file_name.startswith('._'):
                    # file is probably a macOS resource fork, skip
                    continue
                file_list.append((temp_file_path, original_file_relpath))
        return iter(file_list), len(file_list)
