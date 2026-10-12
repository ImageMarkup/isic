import csv
import io

from django.urls import reverse
from playwright.sync_api import expect
import pytest

# The first validation waits for Pyodide to download and install isic-metadata.
_PYODIDE_TIMEOUT = 120_000


def _csv_content(rows):
    content = io.StringIO()
    writer = csv.DictWriter(content, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return content.getvalue()


def _choose_csv(page, name, rows):
    with page.expect_file_chooser() as file_chooser:
        page.get_by_text("Drop a metadata CSV here").click()
    file_chooser.value.set_files(
        {"name": name, "mimeType": "text/csv", "buffer": _csv_content(rows).encode()}
    )


def _drop_csvs(page, files):
    data_transfer = page.evaluate_handle(
        """(files) => {
            const dataTransfer = new DataTransfer();
            for (const [name, content] of files) {
                dataTransfer.items.add(new File([content], name, { type: 'text/csv' }));
            }
            return dataTransfer;
        }""",
        [[name, _csv_content(rows)] for name, rows in files],
    )
    page.get_by_text("Drop a metadata CSV here").dispatch_event(
        "drop", {"dataTransfer": data_transfer}
    )


@pytest.mark.playwright
def test_metadata_validator(context, faker):
    page = context.new_page()
    page.goto(reverse("ingest/metadata-validator"))

    valid_name = faker.file_name(extension="csv")
    _choose_csv(
        page,
        valid_name,
        [
            {"filename": faker.file_name(extension="jpg"), "age": 30, "sex": "male"},
            {"filename": faker.file_name(extension="jpg"), "age": 45, "sex": "female"},
        ],
    )
    expect(page.get_by_text(f"No problems in the 2 rows of {valid_name}.")).to_be_visible(
        timeout=_PYODIDE_TIMEOUT
    )

    invalid_name = faker.file_name(extension="csv")
    lesion_id = faker.pystr()
    unknown_column = faker.pystr()
    invalid_rows = [
        {
            "filename": faker.file_name(extension="jpg"),
            "age": 30,
            "sex": "male",
            "lesion_id": lesion_id,
            "patient_id": faker.pystr(),
            unknown_column: faker.word(),
        },
        {
            "filename": faker.file_name(extension="jpg"),
            "age": "not a number",
            "sex": "female",
            "lesion_id": lesion_id,
            "patient_id": faker.pystr(),
            unknown_column: faker.word(),
        },
        {
            "filename": faker.file_name(extension="jpg"),
            "age": 40,
            "sex": "not a sex",
            "lesion_id": faker.pystr(),
            "patient_id": faker.pystr(),
            unknown_column: faker.word(),
        },
    ]
    _drop_csvs(page, [(invalid_name, invalid_rows), (valid_name, invalid_rows)])
    expect(page.get_by_text("only one CSV can be checked at a time")).to_be_visible()

    _drop_csvs(page, [(invalid_name, invalid_rows)])
    expect(page.get_by_text(f"3 problems in the 3 rows of {invalid_name}.")).to_be_visible()
    for column, row in [("age", "3"), ("sex", "4")]:
        column_row = page.get_by_role("row").filter(
            has=page.get_by_role("cell", name=column, exact=True)
        )
        expect(column_row.get_by_role("cell").last).to_have_text(row)
    expect(page.get_by_role("row").filter(has_text="multiple patients")).to_contain_text(lesion_id)
    expect(page.get_by_text(unknown_column, exact=True)).to_be_visible()
