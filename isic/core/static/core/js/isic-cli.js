function isicCli() {
  return {
    get downloadCommand() {
      const params = (new URL(document.location)).searchParams;
      let base = 'isic image download';

      if (params.has('query')) {
        base += ` --search "${params.get('query').replace(/"/g, '\\\"')}"`;
      }

      if (params.has('collections')) {
        base += ` --collections "${params.getAll('collections').join(',')}"`;
      }

      return base + ' --limit 0 myimages/';
    },
    copyInstallCommand() {
      navigator.clipboard.writeText('pip install isic-cli');
    },
    copyDownloadCommand() {
      navigator.clipboard.writeText(this.downloadCommand);
    }
  }
}
