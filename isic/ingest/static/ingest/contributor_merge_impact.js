// Alpine component for the merge contributors page. It listens for selections from the two
// autocomplete fields, which are otherwise independent components, and loads a summary of who
// gains access to what once both contributors are chosen.
function contributorMergeImpact({ impactUrl, destField, srcField }) {
  return {
    selections: {},
    impact: null,
    loading: false,

    onAutocompleteSelection({ name, id }) {
      if (name !== destField && name !== srcField) return;
      this.selections[name] = id || '';
      this.refresh();
    },

    async refresh() {
      const dest = this.selections[destField] || '';
      const src = this.selections[srcField] || '';

      // merging a contributor into itself is rejected by the form, so there's nothing to warn about
      if (!dest || !src || dest === src) {
        this.impact = null;
        this.loading = false;
        return;
      }

      this.loading = true;
      const params = new URLSearchParams({ dest_contributor: dest, src_contributor: src });
      try {
        const response = await fetch(`${impactUrl}?${params}`);
        this.impact = response.ok ? await response.json() : null;
      } finally {
        this.loading = false;
      }
    },

    get anyoneGainsAccess() {
      return Boolean(
        this.impact &&
          (this.impact.users_gaining_access_to_dest.length ||
            this.impact.users_gaining_access_to_src.length)
      );
    },

    number(count) {
      return new Intl.NumberFormat('en-US').format(count ?? 0);
    },

    pluralize(count, singular, plural) {
      return count === 1 ? singular : plural;
    },
  };
}
