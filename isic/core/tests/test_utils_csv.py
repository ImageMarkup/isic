import csv
import io

from isic.core.utils.csv import FORBIDDEN_LEADING_CHARS, EscapingDictWriter, EscapingWriter


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

    assert reader.fieldnames
    for header in reader.fieldnames:
        assert not any(header.startswith(char) for char in FORBIDDEN_LEADING_CHARS)

    for row in reader:
        for value in row.values():
            assert not any(value.startswith(char) for char in FORBIDDEN_LEADING_CHARS)


def test_escaping_writer_matches_escaping_dict_writer():
    fieldnames = ["=header", "text", "number", "flag", "empty"]
    rows = [
        ["@at", 'a "quote", and a comma', -5, True, None],
        ["+plus", "two\nlines", 3, False, ""],
        ["-minus", "plain", 0, None, "=1+1"],
    ]

    dict_output = io.StringIO()
    dict_writer = EscapingDictWriter(dict_output, fieldnames=fieldnames)
    dict_writer.writeheader()
    dict_writer.writerows(dict(zip(fieldnames, row, strict=True)) for row in rows)

    output = io.StringIO()
    writer = EscapingWriter(output)
    writer.writerow(fieldnames)
    writer.writerows(rows)

    assert output.getvalue() == dict_output.getvalue()

    # strings with a forbidden leading character are escaped, everything else is written as is.
    written_rows = list(csv.reader(io.StringIO(output.getvalue())))
    assert written_rows == [
        ["\t=header", "text", "number", "flag", "empty"],
        ["\t@at", 'a "quote", and a comma', "-5", "True", ""],
        ["\t+plus", "two\nlines", "3", "False", ""],
        ["\t-minus", "plain", "0", "", "\t=1+1"],
    ]
