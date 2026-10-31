import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { getOperations, getSimulations } from '../api/client';
import { Chart } from '../components/Chart';
import {
  AreaSelect,
  date,
  number,
  PageHeading,
  percent,
  QueryState,
  useAreas,
} from '../components/shared';
export function OperationsPage() {
  const areas = useAreas();
  const [params, setParams] = useSearchParams();
  const selected =
    areas.data?.find((a) => a.id === params.get('area'))?.id ?? areas.data?.[0]?.id ?? '';
  const requested = params.get('simulation') ?? undefined;
  const simulations = useQuery({
    queryKey: ['simulations', selected],
    queryFn: ({ signal }) => getSimulations(selected, signal),
    enabled: !!selected,
  });
  const operations = useQuery({
    queryKey: ['operations', selected, requested],
    queryFn: ({ signal }) => getOperations(selected, requested, signal),
    enabled: !!selected && (simulations.data?.items.length ?? 0) > 0,
  });
  const data = operations.data;
  return (
    <>
      <PageHeading eyebrow="ILLUSTRATIVE OPERATIONAL SCENARIOS" title="Operational Analytics">
        Explore simulated route outcomes and issue resolution, separate from geographic rankings.
      </PageHeading>
      <div className="synthetic-banner" role="note">
        <strong>Synthetic data · simulation only</strong>
        <p>
          These are seeded, illustrative scenarios. They are not real fleet data, forecasts or
          evidence of service performance. They never change geographic scores.
        </p>
      </div>
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
            {!!simulations.data?.items.length && (
              <label className="field">
                Simulation run
                <select
                  value={requested ?? simulations.data.items[0]?.id ?? ''}
                  onChange={(e) => setParams({ area: selected, simulation: e.target.value })}
                >
                  {simulations.data.items.map((s) => (
                    <option key={s.id} value={s.id}>
                      Seed {s.seed} · {date(s.created_at)}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <QueryState
            pending={simulations.isPending}
            error={simulations.error}
            retry={() => void simulations.refetch()}
          />
          {simulations.isSuccess && !simulations.data.items.length && (
            <div className="state">
              <strong>No synthetic scenarios yet</strong>
              <p>
                Generate an opt-in scenario with the backend CLI:{' '}
                <code>
                  simulate-area {areas.data.find((a) => a.id === selected)?.slug} --seed 42 --routes
                  500
                </code>
                .
              </p>
            </div>
          )}
          {!!simulations.data?.items.length && (
            <QueryState
              pending={operations.isPending}
              error={operations.error}
              retry={() => void operations.refetch()}
            />
          )}{' '}
          {data && (
            <>
              <div className="stats-grid">
                <article className="stat">
                  <span>Simulated completion rate</span>
                  <strong>{percent(data.completion_rate)}</strong>
                  <small>{number(data.route_count, 0)} simulated route attempts</small>
                </article>
                <article className="stat">
                  <span>Simulated intervention rate</span>
                  <strong>{percent(data.intervention_rate)}</strong>
                  <small>Attempts with at least one intervention</small>
                </article>
                <article className="stat">
                  <span>Mean completed trip</span>
                  <strong>
                    {number(data.mean_trip_duration_minutes)}
                    <small> min</small>
                  </strong>
                  <small>Completed attempts only</small>
                </article>
              </div>
              <div className="two-columns">
                <article className="panel">
                  <h3>Simulated daily completion</h3>
                  <Chart
                    title="Simulated completion trend"
                    axisLabel="Completion (%)"
                    data={[
                      {
                        type: 'scatter',
                        mode: 'lines+markers',
                        x: data.days.map((d) => d.date),
                        y: data.days.map((d) =>
                          d.completion_rate == null ? null : d.completion_rate * 100,
                        ),
                        line: { color: '#39755c' },
                      },
                    ]}
                  />
                </article>
                <article className="panel">
                  <h3>Simulated issues by severity</h3>
                  <Chart
                    title="Simulated issue severity"
                    axisLabel="Issue count"
                    data={[
                      {
                        type: 'bar',
                        x: Object.keys(data.issues_by_severity),
                        y: Object.values(data.issues_by_severity),
                        marker: { color: ['#9db3a0', '#d5b471', '#be7c67'] },
                      },
                    ]}
                  />
                  <p className="small muted">
                    {data.open_issues} open · {data.resolved_issues} resolved ·{' '}
                    {number(data.mean_resolution_hours)} hours mean resolution (resolved issues
                    only).
                  </p>
                </article>
              </div>
              <article className="panel">
                <h3>Daily scenario details · UTC</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Simulated date</th>
                        <th>Attempts</th>
                        <th>Completed</th>
                        <th>Intervention attempts</th>
                        <th>Completion</th>
                        <th>Mean completed duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.days.map((d) => (
                        <tr key={d.date}>
                          <th scope="row">{d.date}</th>
                          <td>{d.routes}</td>
                          <td>{d.completed}</td>
                          <td>{d.interventions}</td>
                          <td>{percent(d.completion_rate)}</td>
                          <td>{number(d.mean_duration_minutes)} min</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
              <article className="panel">
                <h3>Scenario provenance</h3>
                <p className="small muted">
                  Synthetic scenario {data.simulation.id} · Seed {data.simulation.seed} · Generator{' '}
                  {data.simulation.generator_version}
                </p>
                <p className="small muted">
                  Pinned geospatial run {data.simulation.analysis_run_id}. Simulated window begins{' '}
                  {date(data.simulation.simulated_start_at)}. Created{' '}
                  {date(data.simulation.created_at)}.
                </p>
                <pre className="source-data">
                  {JSON.stringify(data.simulation.parameters, null, 2)}
                </pre>
              </article>
            </>
          )}
        </>
      )}
    </>
  );
}
