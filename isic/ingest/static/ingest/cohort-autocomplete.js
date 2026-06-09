function autocompleteInput() {
  return {
    selectedId: '',
    selectedDetail: null,
    loadingSelectedDetail: false,
    query: '',
    suggestions: [],
    loadingSuggestions: false,

    async init() {
      this.selectedId = this.$refs.hiddenInput.defaultValue;
      if (this.selectedId) {
        await this.populateDetail();
        this.query = this.selectedDetail.name;
      }
    },

    async select(item) {
      this.selectedId = item.id;
      this.query = item.name;
      this.suggestions = [];
      await this.populateDetail();
    },

    async populateDetail() {
      this.loadingSelectedDetail = true;
      const response = await fetch(`/api/v2/cohorts/${this.selectedId}/`);
      this.selectedDetail = await response.json();
      this.loadingSelectedDetail = false;
    },

    async fetchSuggestions() {
      this.selectedId = '';
      this.selectedDetail = null;
      this.suggestions = [];
      if (this.query.length >= 3) {
        this.loadingSuggestions = true;
        const response = await fetch(`/api/v2/autocomplete/cohort/?query=${encodeURIComponent(this.query)}`);
        this.suggestions = await response.json();
        this.loadingSuggestions = false;
      }
    },
  };
}
