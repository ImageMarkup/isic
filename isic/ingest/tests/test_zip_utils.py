import zipfile

from isic.ingest import zip_utils

# TODO: Add a more difficult ZIP with skipped content, and use it in these tests


def test_file_names_in_zip(zip_stream_only_images):
    file_names = zip_utils.file_names_in_zip(zip_stream_only_images)

    file_names_list = list(file_names)
    assert len(file_names_list) == 5
    assert 'ISIC_0000000.jpg' in file_names_list


def test_items_in_zip(zip_stream_only_images):
    zip_items = zip_utils.items_in_zip(zip_stream_only_images)

    zip_items_list = list(zip_items)
    assert len(zip_items_list) == 5


def test_items_in_zip_item(zip_stream_only_images):
    zip_items = zip_utils.items_in_zip(zip_stream_only_images)

    zip_item = next(zip_items)
    assert zip_item.name == 'ISIC_0000000.jpg'
    assert isinstance(zip_item.stream, zipfile.ZipExtFile)
    assert zip_item.size == 49982


def test_items_in_zip_read(zip_stream_only_images):
    zip_items = zip_utils.items_in_zip(zip_stream_only_images)
    zip_item = next(zip_items)
    zip_item_content = zip_item.stream.read()

    assert len(zip_item_content) == 49982
    # JFIF files start with FF D8 and end with FF D9
    assert zip_item_content.startswith(b'\xff\xd8')
    assert zip_item_content.endswith(b'\xff\xd9')
