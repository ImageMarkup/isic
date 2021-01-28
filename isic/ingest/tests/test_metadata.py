from pydantic import ValidationError

from isic.ingest.serializers import MetadataRow


def test_melanoma_fields():
    try:
        # mel_class can only be set if diagnosis is melanoma
        MetadataRow(diagnosis='angioma', mel_class='invasive melanoma')
    except ValidationError as e:
        assert len(e.errors()) == 1
        assert e.errors()[0]['loc'][0] == 'mel_class'

    # mel_class can only be set if diagnosis is melanoma
    MetadataRow(diagnosis='melanoma', mel_class='invasive melanoma')


def test_no_benign_melanoma():
    try:
        MetadataRow(diagnosis='melanoma', benign_malignant='benign')
    except ValidationError as e:
        assert len(e.errors()) == 1
        assert e.errors()[0]['loc'][0] == 'diagnosis'
