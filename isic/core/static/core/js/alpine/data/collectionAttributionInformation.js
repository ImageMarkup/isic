import axiosSession from '../../axios.js';

export default (collectionId) => ({
  attributions: [],
  fetched: false,
  loading: false,
  async fetchMetaInformation() {
    this.loading = true;
    const resp = await axiosSession.get(`/api/v2/collections/${collectionId}/attribution/`);

    this.attributions = resp.data;
    this.loading = false;
    this.fetched = true;
  }
});
