import zipfile

import pytest

from isic.ingest import zip_utils


@pytest.fixture
def zip_stream(data_dir):
    with (data_dir / 'ISIC-images.zip').open('rb') as stream:
        yield stream


@pytest.mark.parametrize(
    'path,expected',
    [
        ('', ''),
        ('foo.txt', 'foo.txt'),
        ('foo/bar.txt', 'bar.txt'),
        ('foo/bar/baz', 'baz'),
        ('foo\\bar.txt', 'bar.txt'),
    ],
    ids=['empty', 'root', 'nested', 'nested_2', 'windows'],
)
def test_base_file_name(path, expected):
    file_name = zip_utils._base_file_name(path)
    assert file_name == expected


def test_file_names_in_zip(zip_stream):
    file_names = zip_utils.file_names_in_zip(zip_stream)

    file_names_list = list(file_names)
    assert len(file_names_list) == 83
    assert 'ISIC_0000000.jpg' in file_names_list


def test_items_in_zip(zip_stream):
    zip_items = zip_utils.items_in_zip(zip_stream)

    zip_items_list = list(zip_items)
    assert len(zip_items_list) == 83


def test_items_in_zip_item(zip_stream):
    zip_items = zip_utils.items_in_zip(zip_stream)

    zip_item = next(zip_items)
    assert zip_item.name == 'ISIC_0000000.jpg'
    assert isinstance(zip_item.stream, zipfile.ZipExtFile)
    assert zip_item.size == 49982


def test_items_in_zip_read(zip_stream):
    zip_items = zip_utils.items_in_zip(zip_stream)
    zip_item = next(zip_items)
    zip_item_content = zip_item.stream.read()

    assert len(zip_item_content) == 49982
    # JFIF files start with FF D8 and end with FF D9
    assert zip_item_content.startswith(b'\xff\xd8')
    assert zip_item_content.endswith(b'\xff\xd9')
