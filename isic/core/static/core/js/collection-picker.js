function collectionPicker() {
  return {
    collections: JSON.parse(document.getElementById('collections-ids-names').textContent),
    selectedCollections: [],
    collectionInput: '',
    dropdownOpen: false,

    init() {
      this.selectedCollections = new URLSearchParams(window.location.search)
        .getAll('collections')
        .map(Number)
        .filter(id => !isNaN(id));
    },

    get filteredCollections() {
      const search = this.collectionInput.toLowerCase().trim();
      return this.collections.filter(c =>
        c.name.toLowerCase().includes(search) &&
        !this.selectedCollections.includes(c.id)
      );
    },

    // Focus the input before mutating state so onFocusout sees focus inside the wrapper
    selectCollection(collection) {
      this.$refs.collectionInput.focus();
      this.selectedCollections.push(collection.id);
      this.collectionInput = '';
    },

    removeCollection(id) {
      this.selectedCollections = this.selectedCollections.filter(x => x !== id);
    },

    getCollectionName(id) {
      return this.collections.find(c => c.id === id)?.name ?? '';
    },

    focusNextItem(el) {
      if (el === this.$refs.collectionInput) {
        this.$refs.collectionMenu.querySelector('button')?.focus();
      } else {
        el.closest('li').nextElementSibling?.querySelector('button')?.focus();
      }
    },

    focusPrevItem(el) {
      if (el === this.$refs.collectionInput) return;
      const prev = el.closest('li').previousElementSibling?.querySelector('button');
      if (prev) prev.focus();
      else this.$refs.collectionInput.focus();
    },

    closeDropdown() {
      this.dropdownOpen = false;
      this.$refs.collectionInput.focus();
    },

    onFocusout(event) {
      if (!this.$refs.dropdownWrapper.contains(event.relatedTarget)) {
        this.dropdownOpen = false;
      }
    },
  };
}
