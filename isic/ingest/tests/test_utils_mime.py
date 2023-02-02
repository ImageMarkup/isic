import pathlib

from isic.ingest.utils.mime import guess_mime_type

data_dir = pathlib.Path(__file__).parent / "data"


def test_utils_mime_guess_mime_type_consistent(caplog):
    file_path = data_dir / "ISIC_0000000.jpg"

    with file_path.open("rb") as stream:
        mime_type = guess_mime_type(stream, file_path.name)

    assert mime_type == "image/jpeg"
    assert not any("Inconsistent MIME types" in msg for msg in caplog.messages)


def test_utils_mime_guess_mime_type_inconsistent(caplog):
    file_path = data_dir / "ISIC_0000000.jpg"

    with file_path.open("rb") as stream:
        mime_type = guess_mime_type(stream, "ISIC_0000000.gif")

    assert mime_type == "image/jpeg"
    message = next((msg for msg in caplog.messages if "Inconsistent MIME types" in msg), None)
    assert message
    assert '"image/gif"' in message
