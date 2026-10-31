import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getQuality } from '../api/client';
import { Chart } from '../components/Chart';
import {
  AreaSelect,
  date,
  metricName,
  number,
  PageHeading,
  percent,
  QueryState,
  useAreas,
} from '../components/shared';
export function QualityPage() {
  const areas = useAreas();
  const [params, setParams] = useSearchParams();
  const requested = params.get('area');
  const selected = areas.data?.find((a) => a.id === requested)?.id ?? areas.data?.[0]?.id ?? '';
  const [severity, setSeverity] = useState('all');
  const quality = useQuery({
    queryKey: ['quality', selected],
    queryFn: ({ signal }) => getQuality(selected, signal),
    enabled: !!selected,
  });
  const data = quality.data;
  return (
    <>
      <PageHeading eyebrow="TRUST THE EVIDENCE" title="Data Quality">
        Inspect missing values, reliability signals and the source behind every analysis.
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
              onChange={(id) => setParams({ area: id })}
            />
          </div>
          <QueryState
            pending={quality.isPending}
            error={quality.error}
            retry={() => void quality.refetch()}
          />
          {data && (
            <>
              <div className="stats-grid">
                <article className="stat">
                  <span>Critical findings</span>
                  <strong>{data.finding_counts.critical}</strong>
                  <small>Review before making decisions</small>
                </article>
                <article className="stat">
                  <span>Warnings</span>
                  <strong>{data.finding_counts.warning}</strong>
                  <small>Limitations that need context</small>
                </article>
                <article className="stat">
                  <span>Low-confidence cells</span>
                  <strong>{percent(data.completeness.low_confidence_share)}</strong>
                  <small>
                    {data.completeness.low_confidence_cells} of {data.completeness.cells_count}{' '}
                    cells
                  </small>
                </article>
              </div>
              <article className="panel">
                <div className="panel-heading">
                  <h3>Quality findings</h3>
                  <label className="field">
                    Severity
                    <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                      <option value="all">All findings</option>
                      <option value="critical">Critical</option>
                      <option value="warning">Warning</option>
                      <option value="info">Information</option>
                    </select>
                  </label>
                </div>
                {!data.findings.length && (
                  <p className="small muted">
                    No persisted quality findings for this run. This does not guarantee complete or
                    accurate data.
                  </p>
                )}
                {data.findings
                  .filter((f) => severity === 'all' || f.severity === severity)
                  .map((f, i) => (
                    <div className="finding" key={`${f.rule_key}-${i}`}>
                      <span className={`badge ${f.severity}`}>{f.severity}</span>{' '}
                      <strong className="small">{f.rule_key}</strong>
                      <p>{f.message}</p>
                      {f.affected_fraction != null && (
                        <small className="muted">
                          Affected fraction: {percent(f.affected_fraction)}
                        </small>
                      )}
                    </div>
                  ))}
                {!!data.findings.length &&
                  !data.findings.some((f) => severity === 'all' || f.severity === severity) && (
                    <p className="small muted">No findings match this severity.</p>
                  )}
              </article>
              <article className="panel">
                <h3>Missing metric values</h3>
                <p className="small muted">
                  Cell-level availability, not geographic coverage. Low confidence means any metric
                  confidence below {percent(data.completeness.low_confidence_threshold)}.
                </p>
                <Chart
                  axisLabel="Missing cells"
                  title="Missing cells by metric"
                  data={[
                    {
                      type: 'bar',
                      x: data.completeness.metrics.map((m) => metricName(m.metric)),
                      y: data.completeness.metrics.map((m) => m.null_cells),
                      marker: { color: '#bf9d63' },
                    },
                  ]}
                />
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Missing cells</th>
                        <th>Missing share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.completeness.metrics.map((m) => (
                        <tr key={m.metric}>
                          <th scope="row">{metricName(m.metric)}</th>
                          <td>{number(m.null_cells, 0)}</td>
                          <td>{percent(m.null_share)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
              <article className="panel">
                <div className="panel-heading">
                  <h3>Source & provenance</h3>
                  <span className="badge neutral">PUBLIC DATA</span>
                </div>
                <p className="small">
                  Analyzed {date(data.analyzed_at)} · Pipeline {data.run.pipeline_version}
                </p>
                <p className="small muted">
                  Run {data.run.id} · {data.run.status}
                </p>
                <p className="small muted">
                  Boundary source: {areas.data.find((a) => a.id === selected)?.source}. Road
                  metadata completeness measures tag presence, not geographic coverage. Confidence
                  is a reliability signal, not a probability.
                </p>
                <pre className="source-data">{JSON.stringify(data.source, null, 2)}</pre>
              </article>
            </>
          )}
        </>
      )}
    </>
  );
}
