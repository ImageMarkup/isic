import codecs
import csv
import io
import pathlib

data_dir = pathlib.Path(__file__).parent / "data"

# csv.DictWriter expects a StringIO, but to persist files we need a BytesIO
# This will allow string values to be written to a BytesIO
StreamWriter = codecs.getwriter("utf-8")


def csv_stream_valid() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["filename", "benign_malignant", "foo"])
    writer.writeheader()
    writer.writerow({"filename": "filename.jpg", "benign_malignant": "benign", "foo": "bar"})
    return file_stream


def csv_stream_without_filename_column() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["foo"])
    writer.writeheader()
    writer.writerow({"foo": "bar"})
    return file_stream


def csv_stream_bom_filename_column() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["\ufefffilename"])
    writer.writeheader()
    return file_stream


def csv_stream_duplicate_filenames() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["filename"])
    writer.writeheader()
    writer.writerow({"filename": "foo.jpg"})
    writer.writerow({"filename": "foo.jpg"})
    return file_stream
