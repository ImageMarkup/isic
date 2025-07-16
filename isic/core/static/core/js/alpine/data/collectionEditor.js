import axiosSession from '../../axios.js';

export default (collectionId) => ({
  init() {
    const existingStorage = localStorage.getItem(this.storageKey);
    if (existingStorage !== null) {
      this.images = new Set(JSON.parse(existingStorage));
    }
  },
  storageKey: `images_to_remove_collection_${collectionId}`,
  images: new Set(),
  _imagesToArray() {
    return Array.from(this.images.values())
  },
  _persist() {
    localStorage.setItem(this.storageKey, JSON.stringify(this._imagesToArray()));
  },
  toggleImage(imageId) {
    if (this.images.has(imageId)) {
      this.images.delete(imageId);
    } else {
      this.images.add(imageId);
    }

    this._persist();
  },
  removeImage(imageId) {  // TODO: unused??
    this._persist();
  },
  async deleteImages() {
    if (confirm(`Are you sure you want to remove ${this.images.size} images from this collection?`)) {
      try {
        const resp = await axiosSession.post(`/api/v2/collections/${collectionId}/remove-from-list/`, {
          'isic_ids': this._imagesToArray()
        });
      } catch (error) {
        alert('Something went wrong.');
        return;
      }
      this.resetImages(`/collections/${collectionId}/`);
    }
  },
  resetImages(url) {
    this.images.clear();
    this._persist();
    window.location.reload(url);
  }
});
