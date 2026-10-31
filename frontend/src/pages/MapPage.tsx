import { lazy, Suspense, useCallback, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getCells, getDetail, getMetrics } from '../api/client';
import {
  AreaSelect,
  Confidence,
  date,
  metricName,
  metricNames,
  number,
  PageHeading,
  percent,
  QueryState,
  useAreas,
} from '../components/shared';
const AreaMap = lazy(() => import('../features/map/AreaMap').then((m) => ({ default: m.AreaMap })));
export function MapPage() {
  const areas = useAreas();
  const [params, setParams] = useSearchParams();
  const selected =
    areas.data?.find((a) => a.id === params.get('area'))?.id ?? areas.data?.[0]?.id ?? '';
  const metric = params.get('metric') ?? 'overall_score';
  const validMetric =
    metric === 'overall_score' || metric in metricNames ? metric : 'overall_score';
  const [viewport, setViewport] = useState<{ area: string; bbox: number[] } | null>(null);
  const [lowConfidence, setLowConfidence] = useState(true);
  const [activeCell, setActiveCell] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ['detail', selected],
    queryFn: ({ signal }) => getDetail(selected, signal),
    enabled: !!selected,
  });
  const metrics = useQuery({
    queryKey: ['metrics', selected],
    queryFn: ({ signal }) => getMetrics(selected, signal),
    enabled: !!selected,
  });
  const bbox = viewport?.area === selected ? viewport.bbox : detail.data?.bbox;
  const cells = useQuery({
    queryKey: ['cells', selected, validMetric, bbox],
    queryFn: ({ signal }) => getCells(selected, validMetric, bbox!, signal),
    enabled: !!selected && !!bbox,
  });
  const onViewport = useCallback(
    (bbox: number[]) =>
      setViewport((previous) =>
        previous?.area === selected && previous.bbox.join(',') === bbox.join(',')
          ? previous
          : { area: selected, bbox },
      ),
    [selected],
  );
  const cell = cells.data?.features.find((f) => f.properties.h3_index === activeCell)?.properties;
  const definition = metrics.data?.metrics.find((m) => m.key === validMetric);
  return (
    <>
      <PageHeading eyebrow="THE GEOGRAPHIC PICTURE" title="Interactive Map">
        Explore the road network one cell at a time. Make uncertainty part of the picture.
      </PageHeading>
      <QueryState
        pending={areas.isPending}
        error={areas.error}
        empty={areas.isSuccess && !areas.data.length}
        retry={() => void areas.refetch()}
      />
      {!!areas.data?.length && (
        <>
          <div className="toolbar">
            <AreaSelect
              areas={areas.data}
              value={selected}
              onChange={(id) => setParams({ area: id, metric: validMetric })}
            />
            <label className="field">
              Map metric
              <select
                value={validMetric}
                onChange={(e) => setParams({ area: selected, metric: e.target.value })}
              >
                <option value="overall_score">Overall score</option>
                {Object.keys(metricNames).map((key) => (
                  <option key={key} value={key}>
                    {metricName(key)}
                  </option>
                ))}
              </select>
            </label>
            <label className="small">
              <input
                type="checkbox"
                checked={lowConfidence}
                onChange={(e) => setLowConfidence(e.target.checked)}
              />{' '}
              Outline low-confidence cells
            </label>
          </div>
          <QueryState
            pending={detail.isPending}
            error={detail.error}
            retry={() => void detail.refetch()}
          />
          {detail.data && (
            <div className="map-layout">
              <Suspense fallback={<p className="state">Loading map…</p>}>
                <AreaMap
                  key={selected}
                  detail={detail.data}
                  cells={cells.data}
                  lowConfidence={lowConfidence}
                  onViewport={onViewport}
                  onSelect={setActiveCell}
                />
              </Suspense>
              <aside className="map-panel">
                <article className="panel">
                  <p className="eyebrow">MAP LEGEND</p>
                  <h3>
                    {validMetric === 'overall_score' ? 'Overall score' : metricName(validMetric)}
                  </h3>
                  <div className="legend-ramp" />
                  <div className="legend-labels">
                    <span>Lower</span>
                    <span>Higher</span>
                  </div>
                  <p className="small muted">
                    {validMetric === 'overall_score'
                      ? 'Score: 0–100.'
                      : `${definition?.unit ?? 'Raw units'}; colors use fixed normalized values.`}
                  </p>
                  <p className="small muted">
                    Gray: unavailable. Amber outline: confidence below 50%.
                  </p>
                  <p className="small muted">
                    {definition?.description ??
                      'Weighted score under the default model. Higher values are favored by the model assumptions.'}
                  </p>
                  <p className="small muted">
                    {cells.data?.features.length ?? 0} visible cells · H3 resolution 9 by default
                  </p>
                </article>
                <article className="panel">
                  <p className="eyebrow">CELL INSPECTOR</p>
                  {cell ? (
                    <>
                      <h3 className="small">{cell.h3_index}</h3>
                      <dl>
                        <dt>{validMetric === 'overall_score' ? 'Score / 100' : 'Raw value'}</dt>
                        <dd>
                          {number(validMetric === 'overall_score' ? cell.score : cell.raw_value, 2)}
                        </dd>
                        <dt>Normalized value</dt>
                        <dd>{percent(cell.normalized_value)}</dd>
                        <dt>Boundary overlap</dt>
                        <dd>{percent(cell.overlap_ratio)}</dd>
                      </dl>
                      <Confidence value={cell.confidence} />
                    </>
                  ) : (
                    <p className="small muted">
                      Hover to inspect, or select a cell on the map or in the table.
                    </p>
                  )}
                </article>
              </aside>
            </div>
          )}
          <QueryState
            pending={!!bbox && cells.isPending}
            error={cells.error}
            retry={() => void cells.refetch()}
          />
          {cells.data?.truncated && (
            <p className="warnings" role="status">
              The visible area has more than {cells.data.limit} cells. Zoom in to inspect all cells
              in a smaller viewport.
            </p>
          )}
          {cells.data && (
            <article className="panel">
              <div className="panel-heading">
                <h3>Visible cell values</h3>
                <span className="small muted">
                  First {Math.min(20, cells.data.features.length)} of {cells.data.features.length}{' '}
                  returned cells
                </span>
              </div>
              {!cells.data.features.length ? (
                <p className="small muted">
                  No analysis cells in this viewport. Pan back to the service area.
                </p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>H3 cell</th>
                        <th>{validMetric === 'overall_score' ? 'Score / 100' : 'Raw value'}</th>
                        <th>Confidence</th>
                        <th>Overlap</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cells.data.features.slice(0, 20).map(({ properties: c }) => (
                        <tr key={c.h3_index}>
                          <th scope="row">
                            <button
                              aria-pressed={activeCell === c.h3_index}
                              onClick={() => setActiveCell(c.h3_index)}
                            >
                              {c.h3_index}
                            </button>
                          </th>
                          <td>
                            {number(validMetric === 'overall_score' ? c.score : c.raw_value, 2)}
                          </td>
                          <td>
                            <Confidence value={c.confidence} />
                          </td>
                          <td>{percent(c.overlap_ratio)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          )}
          <QueryState error={metrics.error} retry={() => void metrics.refetch()} />
          {metrics.data && (
            <p className="small muted">
              Analyzed {date(metrics.data.analyzed_at)} · Run {metrics.data.run.id}. Source:{' '}
              {areas.data.find((a) => a.id === selected)?.source} and OpenStreetMap.{' '}
              {definition &&
                `Normalization ${definition.normalization_method} ${definition.version}; reference ${number(definition.ref_min, 2)}–${number(definition.ref_max, 2)}. ${definition.higher_is_better ? 'Higher' : 'Lower'} values are favored.`}
            </p>
          )}
        </>
      )}
    </>
  );
}
