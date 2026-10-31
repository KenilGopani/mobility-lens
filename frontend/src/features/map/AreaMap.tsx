import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type { Cells, Detail } from '../../api/types';
import { number, percent } from '../../components/shared';
import 'maplibre-gl/dist/maplibre-gl.css';
const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
// Let Vite bundle the module worker and its shared imports for dev and production.
maplibregl.setWorkerUrl(workerUrl);
const layers = ['cell-fill', 'cell-outline', 'low-confidence', 'area-boundary'];
export function AreaMap({
  detail,
  cells,
  lowConfidence,
  onViewport,
  onSelect,
}: {
  detail: Detail;
  cells?: Cells;
  lowConfidence: boolean;
  onViewport: (bbox: number[]) => void;
  onSelect: (index: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<maplibregl.Map | null>(null);
  const current = useRef({ cells, lowConfidence, onViewport, onSelect });
  const [notice, setNotice] = useState('');
  useEffect(() => {
    current.current = { cells, lowConfidence, onViewport, onSelect };
    const map = instance.current;
    if (map?.getSource('cells')) {
      (map.getSource('cells') as maplibregl.GeoJSONSource).setData(cells ?? empty);
      map.setLayoutProperty('low-confidence', 'visibility', lowConfidence ? 'visible' : 'none');
    }
  }, [cells, lowConfidence, onViewport, onSelect]);
  useEffect(() => {
    if (!container.current) return;
    let map: maplibregl.Map;
    let popup: maplibregl.Popup | undefined;
    try {
      map = new maplibregl.Map({
        container: container.current,
        style: import.meta.env.VITE_MAP_STYLE_URL || 'https://demotiles.maplibre.org/style.json',
        center: [(detail.bbox[0] + detail.bbox[2]) / 2, (detail.bbox[1] + detail.bbox[3]) / 2],
        zoom: 11,
        minZoom: 4,
        renderWorldCopies: false,
        attributionControl: { compact: true },
      });
      instance.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
      const publishViewport = () => {
        const b = map.getBounds();
        const box = [
          Math.max(-180, b.getWest()),
          Math.max(-90, b.getSouth()),
          Math.min(180, b.getEast()),
          Math.min(90, b.getNorth()),
        ].map((v) => Math.round(v * 1e5) / 1e5);
        if (box[0]! < box[2]! && box[1]! < box[3]!) current.current.onViewport(box);
      };
      map.on('load', () => {
        map.addSource('boundary', {
          type: 'geojson',
          data: { type: 'Feature', geometry: detail.boundary, properties: {} },
        });
        map.addSource('cells', { type: 'geojson', data: current.current.cells ?? empty });
        map.addLayer({
          id: 'cell-fill',
          type: 'fill',
          source: 'cells',
          paint: {
            'fill-color': [
              'case',
              ['all', ['==', ['get', 'score'], null], ['==', ['get', 'normalized_value'], null]],
              '#c4c8c0',
              [
                'interpolate',
                ['linear'],
                [
                  'coalesce',
                  ['get', 'normalized_value'],
                  ['/', ['coalesce', ['get', 'score'], 0], 100],
                ],
                0,
                '#e7edd9',
                0.5,
                '#8eb294',
                1,
                '#245c45',
              ],
            ],
            'fill-opacity': 0.8,
          },
        });
        map.addLayer({
          id: 'cell-outline',
          type: 'line',
          source: 'cells',
          paint: { 'line-color': '#fff', 'line-width': 0.6, 'line-opacity': 0.55 },
        });
        map.addLayer({
          id: 'low-confidence',
          type: 'line',
          source: 'cells',
          filter: ['all', ['!=', ['get', 'confidence'], null], ['<', ['get', 'confidence'], 0.5]],
          layout: { visibility: current.current.lowConfidence ? 'visible' : 'none' },
          paint: { 'line-color': '#b36e2d', 'line-width': 2 },
        });
        map.addLayer({
          id: 'area-boundary',
          type: 'line',
          source: 'boundary',
          paint: { 'line-color': '#284b3b', 'line-width': 2, 'line-dasharray': [3, 2] },
        });
        map.fitBounds(
          [
            [detail.bbox[0], detail.bbox[1]],
            [detail.bbox[2], detail.bbox[3]],
          ],
          { padding: 45, duration: 0 },
        );
        publishViewport();
        map.on('moveend', publishViewport);
      });
      popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on('mousemove', 'cell-fill', (e) => {
        const props = e.features?.[0]?.properties;
        if (!props) return;
        map.getCanvas().style.cursor = 'pointer';
        popup
          ?.setLngLat(e.lngLat)
          .setText(
            `${props.h3_index} · ${number(props.score ?? props.raw_value, 2)} · ${percent(props.confidence)} confidence`,
          )
          .addTo(map);
      });
      map.on('mouseleave', 'cell-fill', () => {
        map.getCanvas().style.cursor = '';
        popup?.remove();
      });
      map.on('click', 'cell-fill', (e) => {
        const index = e.features?.[0]?.properties?.h3_index;
        if (typeof index === 'string') current.current.onSelect(index);
      });
      map.on('error', () =>
        setNotice(
          'The basemap could not fully load. Analysis values remain available in the cell table.',
        ),
      );
    } catch {
      // The accessible cell table remains usable when WebGL is unavailable.
      queueMicrotask(() =>
        setNotice(
          'Interactive map unavailable on this device. Explore the same cells in the table below.',
        ),
      );
    }
    return () => {
      popup?.remove();
      if (instance.current) {
        for (const id of layers) {
          if (instance.current.getLayer(id)) instance.current.removeLayer(id);
        }
        instance.current.remove();
        instance.current = null;
      }
    };
  }, [detail]);
  return (
    <div className="map-container" aria-label="Interactive service area map">
      {notice && (
        <p className="map-notice" role="status">
          {notice}
        </p>
      )}
      <div ref={container} className="map-surface" />
    </div>
  );
}
