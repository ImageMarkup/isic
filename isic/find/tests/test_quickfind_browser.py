from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_quickfind_focuses_search_input(page, live_server):
    page.goto(live_server.url)
    quickfind_input = page.locator("#quickfind-input")

    page.locator("#quickfind-button").click()
    expect(quickfind_input).to_be_focused()

    page.keyboard.press("Escape")
    expect(quickfind_input).not_to_be_focused()

    page.locator("#quickfind-button").click()
    expect(quickfind_input).to_be_focused()

    # Click outside the modal-box (on the overlay) to dismiss
    page.locator("#quickfind-input").evaluate("el => el.closest('.modal').click()")
    expect(quickfind_input).not_to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_quickfind_focus_not_racing_xshow(page, live_server):
    """
    Regression: repeated open/close could leave quickfind unfocused.

    Opening and closing the quickfind modal repeatedly could leave the search
    input unfocused when reopened. The root cause was that Alpine's x-show
    defers its style change to a macrotask, so using $nextTick to focus raced
    with it and could call focus() on a still-hidden element (a silent no-op).
    This verifies that focus() fires only after the modal is visible.
    """
    page.goto(live_server.url)

    was_visible_on_focus = page.evaluate("""async () => {
        const input = document.getElementById('quickfind-input');
        const modal = input.closest('.modal');
        let visibleOnFocus = null;

        const origFocus = input.focus.bind(input);
        input.focus = function() {
            visibleOnFocus = (modal.style.display !== 'none');
            return origFocus();
        };

        document.getElementById('quickfind-button').click();
        await new Promise(r => setTimeout(r, 500));
        input.focus = origFocus;
        return visibleOnFocus;
    }""")
    assert was_visible_on_focus is True
