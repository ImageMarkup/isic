// Alpine component backing the autocomplete form fields, e.g. the merge cohorts/contributors
// pages. suggestUrl returns a list of matches for a query, detailUrl returns a single object
// (by id) to preview, and labelKey names the field that's displayed for a match.
function autocompleteInput({ suggestUrl, detailUrl, labelKey = 'name', required = false }) {
  return {
    selectedId: '',
    selectedDetail: null,
    loadingSelectedDetail: false,
    query: '',
    suggestions: [],
    loadingSuggestions: false,

    // the selection lives in a hidden input, which the browser bars from constraint validation,
    // so the visible search box carries the requirement instead. typing without picking a
    // suggestion clears selectedId, which is what makes this stricter than a plain `required`.
    get validationMessage() {
      return required && !this.selectedId ? 'Select one of the suggested options.' : '';
    },

    async init() {
      this.$watch('selectedDetail', (selection) =>
        this.$dispatch('autocomplete-selected', { selection }),
      );

      this.selectedId = this.$refs.hiddenInput.defaultValue;
      if (this.selectedId) {
        await this.populateDetail();
        this.query = this.label(this.selectedDetail);
      }
    },

    label(item) {
      return item ? item[labelKey] : '';
    },

    async select(item) {
      this.selectedId = item.id;
      this.query = this.label(item);
      this.suggestions = [];
      await this.populateDetail();
    },

    async populateDetail() {
      this.loadingSelectedDetail = true;
      const response = await fetch(`${detailUrl}${this.selectedId}/`);
      this.selectedDetail = await response.json();
      this.loadingSelectedDetail = false;
    },

    async fetchSuggestions() {
      this.selectedId = '';
      this.selectedDetail = null;
      this.suggestions = [];
      if (this.query.length >= 3) {
        this.loadingSuggestions = true;
        const response = await fetch(`${suggestUrl}?query=${encodeURIComponent(this.query)}`);
        this.suggestions = await response.json();
        this.loadingSuggestions = false;
      }
    },
  };
}
