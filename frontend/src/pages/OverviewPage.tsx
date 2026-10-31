import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getSummary } from '../api/client';
import { Chart } from '../components/Chart';
import {
  Confidence,
  date,
  metricName,
  number,
  PageHeading,
  QueryState,
  useAreas,
  Warnings,
} from '../components/shared';
export function OverviewPage() {
  const areas = useAreas();
  const ranked = [...(areas.data ?? [])].sort(
    (a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.name.localeCompare(b.name),
  );
  const leader = ranked.find((a) => a.score != null);
  const summary = useQuery({
    queryKey: ['summary', leader?.id],
    queryFn: ({ signal }) => getSummary(leader!.id, signal),
    enabled: !!leader,
  });
  return (
    <>
      <PageHeading eyebrow="YOUR NEXT MOVE, INFORMED" title="Executive Overview">
        Compare candidate areas. Understand the evidence. Plan the next expansion.
      </PageHeading>
      <QueryState
        pending={areas.isPending}
        error={areas.error}
        empty={areas.isSuccess && !ranked.length}
        retry={() => void areas.refetch()}
      />
      {!!ranked.length && (
        <>
          <div className="stats-grid">
            <article className="stat">
              <span>Candidate areas</span>
              <strong>{ranked.length.toString().padStart(2, '0')}</strong>
              <small>Bay Area service regions</small>
            </article>
            <article className="stat">
              <span>Areas with scores</span>
              <strong>
                {ranked
                  .filter((a) => a.score != null)
                  .length.toString()
                  .padStart(2, '0')}
              </strong>
              <small>Latest successful analyses</small>
            </article>
            <article className="stat">
              <span>Leading score</span>
              <strong>
                {number(leader?.score)}
                <small> / 100</small>
              </strong>
              <small>Deterministic weighted model</small>
            </article>
          </div>
          <div className="overview-grid">
            <article className="recommendation">
              <p className="eyebrow">{leader ? 'LEADING CANDIDATE' : 'ANALYSIS NEEDED'}</p>
              <h3>{leader?.name ?? 'No scored areas yet'}</h3>
              <p>
                {leader
                  ? 'Highest score under the current model. Review the evidence and data quality before making an expansion decision.'
                  : 'Run the analysis pipeline to produce metrics and scores.'}
              </p>
              {leader && (
                <>
                  <Confidence value={leader.confidence} />
                  <p className="small">Analyzed {date(leader.last_run_at)}</p>
                  <Link className="button light" to={`/map?area=${leader.id}`}>
                    Explore this area ↗
                  </Link>
                </>
              )}
            </article>
            <article className="panel">
              <div className="panel-heading">
                <h3>Candidate ranking</h3>
                <span className="muted small">Score / 100</span>
              </div>
              <Chart
                title="Candidate scores"
                data={[
                  {
                    type: 'bar',
                    x: ranked.map((a) => a.name),
                    y: ranked.map((a) => a.score),
                    marker: { color: ranked.map((_, i) => (i === 0 ? '#267963' : '#b5cec0')) },
                    hovertemplate: '%{x}: %{y:.1f}<extra></extra>',
                  },
                ]}
              />
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Service area</th>
                      <th>Score</th>
                      <th>Reliability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((a) => (
                      <tr key={a.id}>
                        <td>{a.rank == null ? '—' : `#${a.rank}`}</td>
                        <th scope="row">{a.name}</th>
                        <td>{number(a.score)}</td>
                        <td>
                          <Confidence value={a.confidence} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
          {leader && (
            <article className="panel">
              <div className="panel-heading">
                <h3>Behind the recommendation</h3>
                <Link to="/comparison">Compare the evidence ↗</Link>
              </div>
              <QueryState
                pending={summary.isPending}
                error={summary.error}
                retry={() => void summary.refetch()}
              />
              {summary.data && (
                <>
                  <div className="metric-grid">
                    {summary.data.components.map((c) => (
                      <div className="metric-card" key={c.metric}>
                        <span>{c.display_name ?? metricName(c.metric)}</span>
                        <strong>{number(c.raw_value, 2)}</strong>
                        <small>
                          {number(c.contribution)} score points · {Math.round(c.weight * 100)}%
                          weight
                        </small>
                      </div>
                    ))}
                  </div>
                  <Warnings warnings={summary.data.warnings} />
                  <p className="muted small">
                    {summary.data.finding_counts.critical} critical findings ·{' '}
                    {summary.data.finding_counts.warning} warnings.{' '}
                    <Link to={`/quality?area=${leader.id}`}>Review data quality</Link>
                  </p>
                  <p className="muted small">
                    Model: {summary.data.scoring_model?.name ?? 'Unavailable'}{' '}
                    {summary.data.scoring_model?.version}. Weights and reference ranges are
                    assumptions; higher values are favored by the baseline model.
                  </p>
                </>
              )}
            </article>
          )}
        </>
      )}
    </>
  );
}
