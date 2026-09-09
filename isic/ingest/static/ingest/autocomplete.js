// Alpine component backing the autocomplete form fields, e.g. the merge cohorts/contributors
// pages. suggestUrl returns a list of matches for a query, detailUrl returns a single object
// (by id) to preview, and labelKey names the field that's displayed for a match.
function autocompleteInput({
  suggestUrl,
  detailUrl,
  labelKey = 'name',
  required = false,
  fieldName = '',
}) {
  return {
    selectedId: '',
    selectedDetail: null,
    loadingSelectedDetail: false,
    query: '',
    suggestions: [],
    loadingSuggestions: false,
    rootEl: null,

    // the selection lives in a hidden input, which the browser bars from constraint validation,
    // so the visible search box carries the requirement instead. typing without picking a
    // suggestion clears selectedId, which is what makes this stricter than a plain `required`.
    get validationMessage() {
      return required && !this.selectedId ? 'Select one of the suggested options.' : '';
    },

    async init() {
      // notifySelection can run after the clicked suggestion has been removed from the DOM, and
      // events dispatched from a detached element never bubble, so hold onto the root element.
      this.rootEl = this.$el;
      this.$watch('selectedDetail', (selection) =>
        this.$dispatch('autocomplete-selected', { selection }),
      );

      this.selectedId = this.$refs.hiddenInput.defaultValue;
      if (this.selectedId) {
        await this.populateDetail();
        this.query = this.label(this.selectedDetail);
      }
      this.notifySelection();
    },

    label(item) {
      return item ? item[labelKey] : '';
    },

    // let an ancestor react to selections made across otherwise independent autocomplete fields,
    // e.g. the contributor merge impact panel. pages without a listener are unaffected.
    notifySelection() {
      this.rootEl.dispatchEvent(
        new CustomEvent('autocomplete-selection', {
          detail: { name: fieldName, id: this.selectedId },
          bubbles: true,
        })
      );
    },

    async select(item) {
      this.selectedId = item.id;
      this.query = this.label(item);
      this.suggestions = [];
      await this.populateDetail();
      this.notifySelection();
    },

    async populateDetail() {
      this.loadingSelectedDetail = true;
      const response = await fetch(`${detailUrl}${this.selectedId}/`);
      this.selectedDetail = await response.json();
      this.loadingSelectedDetail = false;
    },

    async fetchSuggestions() {
      // typing invalidates the selection, but only the first keystroke actually changes it
      const hadSelection = Boolean(this.selectedId);
      this.selectedId = '';
      this.selectedDetail = null;
      this.suggestions = [];
      if (hadSelection) {
        this.notifySelection();
      }
      if (this.query.length >= 3) {
        this.loadingSuggestions = true;
        const response = await fetch(`${suggestUrl}?query=${encodeURIComponent(this.query)}`);
        this.suggestions = await response.json();
        this.loadingSuggestions = false;
      }
    },
  };
}
