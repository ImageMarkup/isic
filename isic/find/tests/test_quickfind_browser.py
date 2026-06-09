from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
def test_quickfind_focuses_search_input(page):
    page.goto("/")
    quickfind_input = page.locator("#quickfind-input")

    page.locator("#quickfind-button").click()
    expect(quickfind_input).to_be_focused()

    # Close and reopen — focus should be restored
    page.keyboard.press("Escape")
    expect(quickfind_input).not_to_be_focused()

    page.locator("#quickfind-button").click()
    expect(quickfind_input).to_be_focused()
