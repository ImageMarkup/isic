export default () => ({
  items: {},
  setReview(id, value) {
    this.items[id] = value;
  },
  addItem(id) {
    this.items[id] = null;
  },
});
