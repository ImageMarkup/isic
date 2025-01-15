import GeoTIFF from 'ol/source/GeoTIFF.js';
import Map from 'ol/Map.js';
import Projection from 'ol/proj/Projection.js';
import TileLayer from 'ol/layer/WebGLTile.js';
import View from 'ol/View.js';
import { getCenter } from 'ol/extent.js';


function initializeCogViewer(target, url, width, height) {
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
        target: target,
        layers: [
            new TileLayer({
                source: geotiff,
            }),
        ],
        view: new View({
            projection: projection,
            center: getCenter(extent),
            extent: extent,
            zoom: .75,
            constrainOnlyCenter: true,
        }),
    });
}

window.initializeCogViewer = initializeCogViewer;
