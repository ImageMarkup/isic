import io
import pathlib
from typing import BinaryIO
import zipfile

data_dir = pathlib.Path(__file__).parent / 'data'


def zip_stream_only_images() -> BinaryIO:
    file_stream = io.BytesIO()

    with zipfile.ZipFile(file_stream, mode='w') as zip_file:
        zip_file.write(data_dir / 'ISIC_0000000.jpg')
        zip_file.write(data_dir / 'ISIC_0000001.jpg')
        zip_file.write(data_dir / 'ISIC_0000002.jpg')
        zip_file.write(data_dir / 'ISIC_0000003.jpg')
        zip_file.write(data_dir / 'ISIC_0000004.jpg')

    return file_stream


def zip_stream_duplicates() -> BinaryIO:
    file_stream = io.BytesIO()

    with zipfile.ZipFile(file_stream, mode='w') as zip_file:
        zip_file.write(data_dir / 'ISIC_0000000.jpg', arcname='a/ISIC_0000000.jpg')
        zip_file.write(data_dir / 'ISIC_0000001.jpg', arcname='a/ISIC_0000001.jpg')
        zip_file.write(data_dir / 'ISIC_0000002.jpg', arcname='a/ISIC_0000002.jpg')

        # Duplicate ISIC_0000000, ISIC_0000002
        zip_file.write(data_dir / 'ISIC_0000000.jpg', arcname='b/ISIC_0000000.jpg')
        zip_file.write(data_dir / 'ISIC_0000002.jpg', arcname='b/ISIC_0000002.jpg')

    return file_stream
