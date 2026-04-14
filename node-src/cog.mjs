import Map from 'ol/Map.js';
import View from 'ol/View.js';
import TileLayer from 'ol/layer/WebGLTile.js';
import GeoTIFF from 'ol/source/GeoTIFF.js';
import ImageLayer from 'ol/layer/Image.js';
import ImageStatic from 'ol/source/ImageStatic.js';
import Projection from 'ol/proj/Projection.js';
import { getCenter } from 'ol/extent.js';

async function initializeCogViewer(target, url) {
  const source = new GeoTIFF({
    sources: [
      {
        url,
        nodata: 0,
      },
    ],
  });
  const view = new View({
    // Use the View factory, as it reads the extents from the image.
    ...(await source.getView()),
    // Allow panning the view past the edges of the image,
    // as long as the center of the view is within the image.
    // This provides a less sticky feeling and makes it easier
    // to zoom near edges of the image, but unfortunately makes
    // the initial zoom a bit too far.
    constrainOnlyCenter: true,
    // Given constrainOnlyCenter, this makes the min zoom a bit more sane.
    // The initial zoom is already 1.
    minZoom: 1,
    // For now, the default Projection works fine, but once physical unit
    // measurements need to be made within the image, we probably need to
    // make a cartesian Projection with appropriate units
  });
  new Map({
    target,
    layers: [new TileLayer({source})],
    view,
  });
}

async function initializeImageViewer(target, url) {
  // ImageStatic requires the image extent upfront, and unlike GeoTIFF there is no
  // embedded metadata OL can read — so we must load the image first to get its dimensions.
  const img = await new Promise((resolve, reject) => {
    const i = new Image();
    i.onload = () => resolve(i);
    i.onerror = reject;
    i.src = url;
  });

  const extent = [0, 0, img.naturalWidth, img.naturalHeight];
  const projection = new Projection({ code: 'raster', units: 'pixels', extent });

  new Map({
    target,
    layers: [new ImageLayer({ source: new ImageStatic({ url, projection, imageExtent: extent }) })],
    view: new View({
      projection,
      center: getCenter(extent),
      zoom: 1,
      minZoom: 0.5,
      maxZoom: 8,
      constrainOnlyCenter: true,
    }),
  });
}

window.initializeCogViewer = initializeCogViewer;
window.initializeImageViewer = initializeImageViewer;
