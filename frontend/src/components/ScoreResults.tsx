import type { AreaScore } from '../api/types';
import { Chart } from './Chart';
import { Confidence, date, metricName, number, percent, Warnings } from './shared';
export const finiteOrNull = (value: number | null | undefined) =>
  value != null && Number.isFinite(value) ? value : null;
const colors = ['#326f58', '#86a685', '#bdcda3', '#d8bd7d', '#a2b8b3'];
export function ScoreResults({ areas }: { areas: AreaScore[] }) {
  const metrics = [...new Set(areas.flatMap((a) => a.components.map((c) => c.metric)))];
  return (
    <>
      <article className="panel">
        <div className="panel-heading">
          <h3>Where the score comes from</h3>
          <span className="small muted">Contributions in score points</span>
        </div>
        <Chart
          title="Score contribution comparison"
          stacked
          data={metrics.map((key, i) => ({
            type: 'bar',
            name: metricName(key),
            x: areas.map((a) => a.name),
            y: areas.map((a) =>
              finiteOrNull(a.components.find((c) => c.metric === key)?.contribution),
            ),
            marker: { color: colors[i % colors.length] },
          }))}
        />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Metric / result</th>
                {areas.map((a) => (
                  <th key={a.service_area_id}>{a.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Overall score / 100</th>
                {areas.map((a) => (
                  <td key={a.service_area_id}>{number(a.score)}</td>
                ))}
              </tr>
              <tr>
                <th scope="row">Rank in selected set</th>
                {areas.map((a) => (
                  <td key={a.service_area_id}>{a.rank == null ? 'Unavailable' : `#${a.rank}`}</td>
                ))}
              </tr>
              <tr>
                <th scope="row">Confidence</th>
                {areas.map((a) => (
                  <td key={a.service_area_id}>
                    <Confidence value={a.confidence} />
                  </td>
                ))}
              </tr>
              {metrics.map((key) => (
                <tr key={key}>
                  <th scope="row">
                    {metricName(key)}
                    <br />
                    <span className="small muted">Raw / normalized / points</span>
                  </th>
                  {areas.map((a) => {
                    const c = a.components.find((c) => c.metric === key);
                    return (
                      <td key={a.service_area_id}>
                        {number(c?.raw_value, 2)} / {percent(c?.normalized_value)} /{' '}
                        {number(c?.contribution)}
                        <br />
                        <span className="muted">
                          Effective weight {percent(c?.effective_weight)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr>
                <th scope="row">Last analysis</th>
                {areas.map((a) => (
                  <td key={a.service_area_id}>{date(a.run?.completed_at)}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </article>
      <div className="metric-grid">
        {areas.map((a) => (
          <article className="panel" key={a.service_area_id}>
            <h3>{a.name}</h3>
            <h4>Strengths</h4>
            {a.strengths.length ? (
              <ul>
                {a.strengths.map((h) => (
                  <li className="small" key={h.metric}>
                    {h.display_name ?? metricName(h.metric)} · {number(h.raw_value, 2)} {h.unit}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="small muted">Unavailable</p>
            )}
            <h4>Risks</h4>
            {a.risks.length ? (
              <ul>
                {a.risks.map((h) => (
                  <li className="small" key={h.metric}>
                    {h.display_name ?? metricName(h.metric)} · {number(h.raw_value, 2)} {h.unit}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="small muted">Unavailable</p>
            )}
            <Warnings warnings={a.warnings} />
          </article>
        ))}
      </div>
    </>
  );
}
