import GeoTIFF from 'ol/source/GeoTIFF.js';
import Map from 'ol/Map.js';
import Projection from 'ol/proj/Projection.js';
import TileLayer from 'ol/layer/WebGLTile.js';
import View from 'ol/View.js';
import { getCenter } from 'ol/extent.js';

// TODO: figure out how to override getOrigin, see
// https://github.com/geotiffjs/geotiff.js/blob/da936684e30ef994f1d0d1e2da844b0e9a6c3cd0/src/geotiffimage.js#L825.
// This will obviate the need for exif stripping the model transformation tag.

function initializeCogViewer(url, width, height) {
    const extent = [0, 0, width, height];

    const projection = new Projection({
        code: 'custom',
        units: 'pixels',
        extent: extent,
    });

    const geotiff = new GeoTIFF({
        sources: [
            {
                url: url,
                nodata: 0,
            },
        ],
    });

    const map = new Map({
        target: 'image',
        layers: [
            new TileLayer({
                source: geotiff,
            }),
        ],
        view: new View({
            projection: projection,
            center: getCenter(extent),
            extent: extent,
            zoom: 1,
        }),
    });
}

window.initializeCogViewer = initializeCogViewer;
