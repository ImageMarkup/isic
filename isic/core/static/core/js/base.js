import Alpine from 'alpinejs';

import accessions from './alpine/accessionsStore.js';

import collectionDetail from './alpine/data/collectionDetail.js';
import collectionEditor from './alpine/data/collectionEditor.js';
import thumbnailGrid from './alpine/data/thumbnailGrid.js';
import quickfind from './alpine/data/quickfind.js';


document.addEventListener('alpine:init', () => {
  Alpine.store('accessions', accessions);

  Alpine.data('collectionDetail', collectionDetail);
  Alpine.data('collectionEditor', collectionEditor);
  Alpine.data('thumbnailGrid', thumbnailGrid);
  Alpine.data('quickfind', quickfind);
});
Alpine.start()
