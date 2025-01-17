import Map from 'ol/Map.js';
import View from 'ol/View.js';
import TileLayer from 'ol/layer/WebGLTile.js';
import GeoTIFF from 'ol/source/GeoTIFF.js';

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

window.initializeCogViewer = initializeCogViewer;
