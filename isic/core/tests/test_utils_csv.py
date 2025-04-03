import csv
import io

from isic.core.utils.csv import FORBIDDEN_LEADING_CHARS, EscapingDictWriter


def test_escaping_dict_writer():
    rows = [
        {
            "sex": "+male",
            "benign_malignant": "=benign",
            "patient_note": "=2+5",
            "=a malicious header even": "something",
            "foo": "=something,with,commas",
        },
        {
            "sex": "female",
            "benign_malignant": "@malignant",
            "patient_note": "=2+5",
            "=a malicious header even": "something",
            "foo": "=something,with,commas",
        },
    ]

    output = io.StringIO()
    writer = EscapingDictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    output.seek(0)
    reader = csv.DictReader(output)

    for header in reader.fieldnames:
        assert not any(header.startswith(char) for char in FORBIDDEN_LEADING_CHARS)

    for row in reader:
        for value in row.values():
            assert not any(value.startswith(char) for char in FORBIDDEN_LEADING_CHARS)
