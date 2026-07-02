from django.template.defaultfilters import slugify
from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.models.doi import DraftDoi
from isic.core.services.collection.image import add_images_to_collection


@pytest.mark.playwright
@pytest.mark.usefixtures(
    "_mock_datacite_create_draft_doi",
    "mock_fetch_doi_citations",
    "mock_fetch_doi_schema_org_dataset",
)
def test_doi_creation_form_related_identifiers_and_submit(
    staff_authenticated_page, collection_factory, image_factory
):
    page = staff_authenticated_page

    collection = collection_factory(public=True, locked=False)
    for _ in range(3):
        add_images_to_collection(collection=collection, image=image_factory(public=True))

    page.goto(reverse("core/collection-create-doi", args=[collection.pk]))

    # Description should be pre-populated from the collection
    expect(page.get_by_label("Description")).to_have_value(collection.description)

    # -- IsDescribedBy: unique constraint --
    add_descriptor_btn = page.get_by_role("button", name="Add Descriptor")
    described_section = add_descriptor_btn.locator("xpath=../..")
    expect(add_descriptor_btn).to_be_enabled()

    add_descriptor_btn.click()

    # After adding one, the button should be disabled (unique constraint)
    expect(add_descriptor_btn).to_be_disabled()

    # Fill in the descriptor: select DOI type and enter a DOI value
    descriptor_doi = f"10.1000/descriptor-{collection.pk}"
    described_section.get_by_role("combobox").select_option("DOI")
    described_section.get_by_role("textbox").fill(descriptor_doi)

    # -- IsReferencedBy: add, fill, and remove --
    add_reference_btn = page.get_by_role("button", name="Add Reference")
    referenced_section = add_reference_btn.locator("xpath=../..")
    add_reference_btn.click()

    # Fill in a URL type reference
    reference_url = f"https://example.com/reference-{collection.pk}"
    referenced_section.get_by_role("combobox").first.select_option("URL")
    referenced_section.get_by_role("textbox").first.fill(reference_url)

    # Add a second reference
    reference_doi = f"10.1000/ref-{collection.pk}"
    add_reference_btn.click()
    referenced_section.get_by_role("combobox").nth(1).select_option("DOI")
    referenced_section.get_by_role("textbox").nth(1).fill(reference_doi)

    # Remove the first reference (the URL one)
    referenced_section.get_by_role("button", name="\u00d7").first.click()

    # Only the DOI reference should remain
    expect(referenced_section.get_by_role("combobox")).to_have_count(1)
    expect(referenced_section.get_by_role("textbox")).to_have_count(1)

    # -- IsSupplementedBy: add one --
    add_supplement_btn = page.get_by_role("button", name="Add Supplement")
    supplemented_section = add_supplement_btn.locator("xpath=../..")
    add_supplement_btn.click()
    supplement_url = f"https://github.com/example/repo-{collection.pk}"
    supplemented_section.get_by_role("combobox").select_option("URL")
    supplemented_section.get_by_role("textbox").fill(supplement_url)

    # Submit the form
    page.get_by_role("button", name="Create Draft DOI").click()

    # Should redirect to the DOI detail page
    expected_slug = slugify(collection.name)
    page.wait_for_url(f"**{reverse('core/doi-detail', kwargs={'slug': expected_slug})}")

    # Verify DOI detail page content
    expect(page.get_by_text("Draft DOI", exact=True)).to_be_visible()
    expect(page.get_by_text(collection.name).first).to_be_visible()

    # Verify the identifiers appear on the detail page
    expect(page.get_by_text(descriptor_doi)).to_be_visible()
    expect(page.get_by_text(reference_doi)).to_be_visible()
    expect(page.get_by_text(supplement_url)).to_be_visible()


@pytest.mark.playwright
@pytest.mark.usefixtures(
    "_mock_datacite_create_draft_doi",
    "mock_fetch_doi_citations",
    "mock_fetch_doi_schema_org_dataset",
)
def test_doi_creation_form_with_supplemental_file(
    staff_authenticated_page, collection_factory, image_factory
):
    page = staff_authenticated_page

    collection = collection_factory(public=True, locked=False)
    for _ in range(3):
        add_images_to_collection(collection=collection, image=image_factory(public=True))

    page.goto(reverse("core/collection-create-doi", args=[collection.pk]))

    # The submit button starts enabled (no in-progress uploads).
    submit_button = page.get_by_role("button", name="Create Draft DOI")
    expect(submit_button).to_be_enabled()

    # Upload a supplemental file through the hidden file input. This triggers the real
    # django-s3-file-field upload to storage; the submit button is disabled until it finishes.
    supplement_filename = f"supplement-{collection.pk}.csv"
    page.locator("#file-input").set_input_files(
        files=[
            {
                "name": supplement_filename,
                "mimeType": "text/csv",
                "buffer": b"lesion_id,diagnosis\n1,melanoma\n",
            }
        ]
    )

    # The uploaded file should show up in the files table with its name and size.
    expect(page.get_by_role("cell", name=supplement_filename)).to_be_visible()

    # A description is required for each supplemental file.
    supplement_description = f"Supplemental metadata for {collection.name}"
    page.get_by_placeholder("Description", exact=True).fill(supplement_description)

    # Once the S3 upload completes, the submit button becomes enabled again.
    expect(submit_button).to_be_enabled()

    submit_button.click()

    # Should redirect to the DOI detail page.
    expected_slug = slugify(collection.name)
    page.wait_for_url(f"**{reverse('core/doi-detail', kwargs={'slug': expected_slug})}")

    expect(page.get_by_text("Draft DOI", exact=True)).to_be_visible()

    # The supplemental file should be listed on the detail page.
    expect(page.get_by_text(supplement_description)).to_be_visible()

    # And it should have been persisted correctly.
    draft_doi = DraftDoi.objects.get(collection=collection)
    supplemental_file = draft_doi.supplemental_files.get()
    assert supplemental_file.filename == supplement_filename
    assert supplemental_file.description == supplement_description
    assert supplemental_file.size > 0
