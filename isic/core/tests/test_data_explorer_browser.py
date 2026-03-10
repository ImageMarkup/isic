from datetime import UTC, datetime
from pathlib import Path
import tempfile
from urllib.parse import quote

from django.core.files.storage import storages
from django.urls import reverse
from playwright.sync_api import expect
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from isic.ingest.utils.parquet import build_parquet_schema


def _build_test_parquet() -> Path:
    schema = build_parquet_schema(
        parquet_metadata={"snapshot_timestamp": datetime.now(tz=UTC).isoformat()}
    )
    rows = [
        {
            "isic_id": f"ISIC_{i:07d}",
            "attribution": "Test Attribution",
            "copyright_license": "CC-0",
            "diagnosis_1": "Malignant" if i % 2 == 0 else "Benign",
            "age_approx": 45 + i,
            "sex": "male" if i % 2 == 0 else "female",
            "anatom_site_general": "anterior torso",
        }
        for i in range(10)
    ]
    table = pa.Table.from_pylist(rows, schema=schema)
    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)  # noqa: SIM115
    pq.write_table(table, tmp.name, compression="snappy")
    tmp.close()
    return Path(tmp.name)


@pytest.fixture
def data_explorer_parquet(settings):
    parquet_path = _build_test_parquet()

    storage = storages["sponsored"]
    key = settings.ISIC_DATA_EXPLORER_PARQUET_KEY
    with parquet_path.open("rb") as f:
        storage.save(key, f)

    original_base_url = storage.base_url
    storage.base_url = f"{storage.endpoint_url}/{storage.bucket_name}"

    yield

    storage.base_url = original_base_url
    storage.delete(key)
    parquet_path.unlink(missing_ok=True)


def _wait_for_ready(page):
    expect(page.locator("#data-explorer-main")).not_to_have_css("display", "none", timeout=60_000)


def _set_query(page, query):
    # CodeMirror replaces the textarea with a custom DOM, so there's no input element to type into
    alpine = "Alpine.$data(document.querySelector('[x-data*=\"dataExplorer\"]'))"
    page.evaluate(f"{alpine}.setQuery({query!r})")


def _click_run_query(page):
    page.locator("#run-query-btn").click()


def _run_query(page, query):
    _set_query(page, query)
    _click_run_query(page)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_loads_and_runs_query(page, live_server, data_explorer_parquet):
    page.goto(f"{live_server.url}{reverse('core/data-explorer')}", timeout=30_000)
    _wait_for_ready(page)

    expect(page.locator("#data-explorer-main")).to_contain_text("10 images")

    _run_query(
        page,
        "SELECT diagnosis_1, COUNT(*) AS count FROM metadata "
        "GROUP BY diagnosis_1 ORDER BY count DESC",
    )

    results = page.locator("#query-results")
    expect(results).to_contain_text("diagnosis_1")
    expect(results).to_contain_text("Malignant")
    expect(results).to_contain_text("Benign")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_shows_error_for_bad_query(page, live_server, data_explorer_parquet):
    page.goto(f"{live_server.url}{reverse('core/data-explorer')}", timeout=30_000)
    _wait_for_ready(page)

    _run_query(page, "SELECT * FROM nonexistent_table")

    expect(page.locator("#query-error")).to_contain_text("nonexistent_table", timeout=30_000)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_example_query(page, live_server, data_explorer_parquet):
    page.goto(f"{live_server.url}{reverse('core/data-explorer')}", timeout=30_000)
    _wait_for_ready(page)

    _run_query(
        page,
        "SELECT sex, ROUND(AVG(age_approx), 1) AS avg_age, COUNT(*) AS count "
        "FROM metadata GROUP BY sex",
    )

    results = page.locator("#query-results")
    expect(results).to_contain_text("avg_age")
    expect(results).to_contain_text("male")
    expect(results).to_contain_text("female")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_query_sharing_via_link(page, live_server, data_explorer_parquet):
    query = "SELECT sex, COUNT(*) AS count FROM metadata GROUP BY sex ORDER BY count DESC"
    page.goto(
        f"{live_server.url}{reverse('core/data-explorer')}?q={quote(query)}",
        timeout=30_000,
    )
    _wait_for_ready(page)

    results = page.locator("#query-results")
    expect(results).to_contain_text("male")
    expect(results).to_contain_text("female")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_no_parquet_shows_error(page, live_server):
    page.goto(f"{live_server.url}{reverse('core/data-explorer')}")

    expect(page.locator("body")).to_contain_text("Failed to initialize", timeout=30_000)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_data_explorer_create_collection_focuses_name_input(
    authenticated_page, live_server, data_explorer_parquet
):
    page = authenticated_page
    page.goto(f"{live_server.url}{reverse('core/data-explorer')}", timeout=30_000)
    _wait_for_ready(page)

    _run_query(page, "SELECT isic_id FROM metadata")
    results = page.locator("#query-results")
    expect(results).to_contain_text("ISIC_", timeout=30_000)

    create_btn = page.locator("#create-collection-btn")
    expect(create_btn).to_be_enabled(timeout=30_000)
    create_btn.click()

    name_input = page.locator("#collection-name-input")
    expect(name_input).to_be_visible()
    expect(name_input).to_be_focused()
