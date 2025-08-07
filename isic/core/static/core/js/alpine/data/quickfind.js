const controller = new AbortController();

export default () => ({
  quickfindOpen: false,
  findText: '',
  results: {},
  openQuickfindModal() {
    this.$nextTick(() => this.$refs.quickfind.focus());
    this.quickfindOpen = true;
  },
  closeQuickfindModal() {
    this.quickfindOpen = false;
  },
  async performFind() {
    if (this.findText.length < 3) {
      this.results = {};
      return;
    }

    const { data } = await axiosSession.get(`/api/v2/quickfind/?query=${this.findText}`, {
      signal: controller.signal,
    });
    this.results = data;
  },
});
