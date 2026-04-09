from django.db import connection
from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.models.doi import DoiRelatedIdentifier, RelatedIdentifierType, RelationType
from isic.core.models.supplemental_file import SupplementalFile
from isic.core.services.collection.image import collection_add_images


def _refresh_collection_counts():
    with connection.cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW materialized_collection_counts;")


def _build_url(**params):
    base = reverse("core/collection-list")
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{qs}"


@pytest.mark.playwright
def test_collection_list_desktop(
    staff_authenticated_page,
    collection_factory,
    doi_factory,
    image_factory,
):
    page = staff_authenticated_page

    # Collections with varying properties to fill the table
    collection_with_doi = collection_factory(public=True, pinned=False, locked=False)
    collection_factory(public=False, pinned=False, locked=False)
    collection_pinned = collection_factory(public=True, pinned=True, locked=False)
    collection_no_doi = collection_factory(public=True, pinned=False, locked=False)
    collection_factory(public=False, pinned=False, locked=False)
    collection_many_images = collection_factory(public=True, pinned=False, locked=False)

    for img in [image_factory(public=True) for _ in range(3)]:
        collection_add_images(collection=collection_with_doi, image=img)

    for img in [image_factory(public=True) for _ in range(7)]:
        collection_add_images(collection=collection_many_images, image=img)

    _refresh_collection_counts()

    doi = doi_factory(collection=collection_with_doi)
    SupplementalFile.objects.create(
        doi=doi, description="Data dictionary", filename="data_dict.csv", size=2048, blob=""
    )
    SupplementalFile.objects.create(
        doi=doi, description="Readme", filename="readme.txt", size=512, blob=""
    )
    DoiRelatedIdentifier.objects.create(
        doi=doi,
        relation_type=RelationType.IS_DESCRIBED_BY,
        related_identifier_type=RelatedIdentifierType.URL,
        related_identifier="https://example.com/paper",
    )

    page.goto(_build_url(exclude_empty=0, exclude_magic=1))

    # All four column headers are visible on desktop
    expect(page.get_by_role("columnheader", name="Created")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Name")).to_be_visible()
    expect(page.get_by_role("columnheader", name="DOI")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Images")).to_be_visible()

    # Private badge on private collections
    rows = page.locator("tbody tr")
    private_badges = page.locator("tbody").get_by_text("Private")
    expect(private_badges).to_have_count(2)

    # Pinned icon shows for pinned collection
    pinned_row = rows.filter(has_text=collection_pinned.name)
    expect(pinned_row.locator(".ri-pushpin-2-fill")).to_be_visible()

    # DOI info: supplemental file count and related identifier shown
    doi_row = rows.filter(has_text=collection_with_doi.name)
    expect(doi_row.get_by_text(doi.id)).to_be_visible()
    expect(doi_row.get_by_text("2 supplemental files")).to_be_visible()
    expect(doi_row.get_by_text("Is Described By: https://example.com/paper")).to_be_visible()

    # No DOI shows dash
    no_doi_row = rows.filter(has_text=collection_no_doi.name)
    expect(no_doi_row.locator("td").nth(2)).to_have_text("-")

    # Image counts populated from materialized view
    expect(doi_row.get_by_role("cell", name="3", exact=True)).to_be_visible()
    many_images_row = rows.filter(has_text=collection_many_images.name)
    expect(many_images_row.get_by_role("cell", name="7", exact=True)).to_be_visible()

    # Sorting by images descending puts most-images collection first
    page.get_by_role("columnheader", name="Images").get_by_role("link").click()
    page.wait_for_url("**/collections/?*sort=images*")
    page.get_by_role("columnheader", name="Images").get_by_role("link").click()
    page.wait_for_url("**/collections/?*order=desc*")

    first_name_cell = page.locator("tbody tr").first.locator("td").nth(1)
    expect(first_name_cell).to_contain_text(collection_many_images.name)

    # Reset sort link appears and navigates back to default
    expect(page.get_by_role("link", name="Reset sort")).to_be_visible()
    page.get_by_role("link", name="Reset sort").click()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Reset sort")).not_to_be_visible()


@pytest.mark.playwright
def test_collection_list_mobile(
    new_context,
    live_server,
    staff_authenticated_user,
    collection_factory,
    doi_factory,
    image_factory,
):
    collection_public = collection_factory(public=True, pinned=False, locked=False)
    collection_private = collection_factory(public=False, pinned=False, locked=False)

    for img in [image_factory(public=True) for _ in range(4)]:
        collection_add_images(collection=collection_public, image=img)

    _refresh_collection_counts()

    doi_factory(collection=collection_public)

    from django.test import Client

    client = Client()
    client.force_login(staff_authenticated_user)
    session_cookie = client.cookies["sessionid"]

    ctx = new_context(
        base_url=live_server.url,
        viewport={"width": 375, "height": 667},
    )
    ctx.add_cookies([{"name": "sessionid", "value": session_cookie.value, "url": live_server.url}])
    page = ctx.new_page()

    page.goto(_build_url(exclude_empty=0, exclude_magic=1))

    # Name column is visible on mobile
    expect(page.get_by_role("columnheader", name="Name")).to_be_visible()

    # Created, DOI, and Images column headers are hidden on mobile
    expect(page.get_by_role("columnheader", name="Created")).not_to_be_visible()
    expect(page.get_by_role("columnheader", name="DOI")).not_to_be_visible()
    expect(page.get_by_role("columnheader", name="Images")).not_to_be_visible()

    # Created date and image count appear as secondary text under the name
    public_row = page.locator("tbody tr").filter(has_text=collection_public.name)
    expect(public_row.locator(".sm\\:hidden")).to_be_visible()
    expect(public_row.locator(".sm\\:hidden")).to_contain_text(
        collection_public.created.strftime("%Y-%m-%d")
    )
    expect(public_row.locator(".sm\\:hidden")).to_contain_text("4 images")

    # Private badge still visible on mobile
    expect(
        page.locator("tbody tr").filter(has_text=collection_private.name).get_by_text("Private")
    ).to_be_visible()
