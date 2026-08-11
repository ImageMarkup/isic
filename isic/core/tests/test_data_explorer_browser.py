from datetime import UTC, datetime
from pathlib import Path
import tempfile

from django.core.files.storage import storages
from django.urls import reverse
from playwright.sync_api import expect
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from isic.ingest.utils.parquet import build_parquet_schema


def _build_test_parquet() -> tuple[Path, list[str]]:
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
            "anatom_site_1": "Trunk",
        }
        for i in range(10)
    ]
    table = pa.Table.from_pylist(rows, schema=schema)
    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)  # noqa: SIM115
    pq.write_table(table, tmp.name, compression="snappy")
    tmp.close()
    return Path(tmp.name), [row["isic_id"] for row in rows]


@pytest.fixture
def data_explorer_parquet(settings):
    """Load a parquet snapshot into storage, yielding the ISIC IDs it contains."""
    parquet_path, isic_ids = _build_test_parquet()

    storage = storages["sponsored"]
    key = settings.ISIC_DATA_EXPLORER_PARQUET_KEY
    with parquet_path.open("rb") as f:
        storage.save(key, f)

    original_base_url = storage.base_url
    storage.base_url = f"{storage.endpoint_url}/{storage.bucket_name}"

    try:
        yield isic_ids
    finally:
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
def test_data_explorer_loads_and_runs_query(page, data_explorer_parquet):
    page.goto(reverse("core/data-explorer"), timeout=30_000)
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
def test_data_explorer_shows_error_for_bad_query(page, data_explorer_parquet):
    page.goto(reverse("core/data-explorer"), timeout=30_000)
    _wait_for_ready(page)

    _run_query(page, "SELECT * FROM nonexistent_table")

    expect(page.locator("#query-error")).to_contain_text("nonexistent_table", timeout=30_000)


@pytest.mark.playwright
def test_data_explorer_example_query(page, data_explorer_parquet):
    page.goto(reverse("core/data-explorer"), timeout=30_000)
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
def test_data_explorer_query_sharing_via_link(page, data_explorer_parquet):
    query = "SELECT sex, COUNT(*) AS count FROM metadata GROUP BY sex ORDER BY count DESC"
    page.goto(
        reverse("core/data-explorer", query={"q": query}),
        timeout=30_000,
    )
    _wait_for_ready(page)
    _click_run_query(page)

    results = page.locator("#query-results")
    expect(results).to_contain_text("male")
    expect(results).to_contain_text("female")


@pytest.mark.playwright
def test_data_explorer_no_parquet_shows_error(page):
    page.goto(reverse("core/data-explorer"))

    expect(page.locator("body")).to_contain_text("Failed to initialize", timeout=30_000)


def _open_collection_modal(page):
    _run_query(page, "SELECT isic_id FROM metadata")
    expect(page.locator("#query-results")).to_contain_text("ISIC_", timeout=30_000)

    add_btn = page.locator("#add-to-collection-btn")
    expect(add_btn).to_be_enabled(timeout=30_000)
    add_btn.click()


@pytest.mark.playwright
def test_data_explorer_collection_modal_focuses_active_tab_input(
    authenticated_page, data_explorer_parquet
):
    page = authenticated_page
    page.goto(reverse("core/data-explorer"), timeout=30_000)
    _wait_for_ready(page)

    _open_collection_modal(page)

    name_input = page.locator("#collection-name-input")
    search_input = page.locator("#collection-search-input")

    expect(name_input).to_be_visible()
    expect(name_input).to_be_focused()

    page.get_by_role("tab", name="Existing Collection").click()
    expect(search_input).to_be_visible()
    expect(search_input).to_be_focused()

    page.get_by_role("tab", name="New Collection").click()
    expect(name_input).to_be_focused()

    # reopening resets to the new collection tab and focuses its input again
    page.get_by_role("tab", name="Existing Collection").click()
    expect(search_input).to_be_focused()
    page.keyboard.press("Escape")

    _open_collection_modal(page)
    expect(name_input).to_be_focused()


@pytest.mark.playwright
def test_data_explorer_add_results_to_existing_collection(
    authenticated_page,
    authenticated_user,
    data_explorer_parquet,
    collection_factory,
    image_factory,
):
    page = authenticated_page
    isic_ids = data_explorer_parquet
    collection = collection_factory(creator=authenticated_user, public=False, locked=False)
    for isic_id in isic_ids:
        image_factory(public=True, isic__id=isic_id)

    page.goto(reverse("core/data-explorer"), timeout=30_000)
    _wait_for_ready(page)

    _open_collection_modal(page)

    page.get_by_role("tab", name="Existing Collection").click()

    # the collection is listed as a recent collection before any search happens
    page.get_by_role("button", name=collection.name).click()
    page.locator("#add-to-existing-collection-btn").click()

    page.wait_for_url(f"**{reverse('core/collection-detail', args=[collection.pk])}")
    expect(page.get_by_text(f"Adding {len(isic_ids)} images")).to_be_visible()
    assert set(collection.images.values_list("isic_id", flat=True)) == set(isic_ids)


@pytest.mark.playwright
def test_data_explorer_search_finds_existing_collection(
    authenticated_page,
    authenticated_user,
    data_explorer_parquet,
    collection_factory,
):
    page = authenticated_page
    # more collections than the recent list holds, so the target is only reachable by searching
    collections = [
        collection_factory(creator=authenticated_user, public=False, locked=False) for _ in range(6)
    ]
    target = collections[0]

    page.goto(reverse("core/data-explorer"), timeout=30_000)
    _wait_for_ready(page)

    _open_collection_modal(page)

    page.get_by_role("tab", name="Existing Collection").click()
    expect(page.get_by_role("button", name=target.name)).not_to_be_visible()

    page.locator("#collection-search-input").fill(target.name)
    expect(page.get_by_role("button", name=target.name)).to_be_visible(timeout=10_000)
