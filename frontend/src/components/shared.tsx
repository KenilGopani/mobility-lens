import { useQuery } from '@tanstack/react-query';
import { getAreas } from '../api/client';

export const metricNames: Record<string, string> = {
  intersection_density: 'Intersection density',
  road_density: 'Road density',
  avg_node_degree: 'Connectivity',
  network_directness: 'Network directness',
  metadata_completeness: 'Metadata completeness',
};
export const metricName = (key: string) => metricNames[key] ?? key.replaceAll('_', ' ');
export const number = (value: number | null | undefined, digits = 1) =>
  value == null || !Number.isFinite(value)
    ? 'Unavailable'
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
export const percent = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value) ? 'Unavailable' : `${number(value * 100, 0)}%`;
export const date = (value: string | null | undefined) =>
  value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Unavailable';
export function useAreas() {
  return useQuery({
    queryKey: ['areas'],
    queryFn: ({ signal }) => getAreas(signal),
    staleTime: 60_000,
  });
}
export function Confidence({ value }: { value: number | null }) {
  return (
    <span className={`badge ${value == null ? 'neutral' : value < 0.5 ? 'warning' : 'success'}`}>
      {percent(value)} confidence
    </span>
  );
}
export function QueryState({
  pending,
  error,
  empty = false,
  retry,
}: {
  pending?: boolean;
  error?: Error | null;
  empty?: boolean;
  retry?: () => void;
}) {
  if (pending)
    return (
      <div className="state" role="status">
        Loading analysis…
      </div>
    );
  if (error)
    return (
      <div className="state error" role="alert">
        <strong>Analysis unavailable</strong>
        <p>{error.message}</p>
        {retry && <button onClick={retry}>Try again</button>}
      </div>
    );
  if (empty)
    return (
      <div className="state">
        <strong>No service areas yet</strong>
        <p>Seed service areas and run an analysis from the backend CLI to get started.</p>
      </div>
    );
  return null;
}
export function AreaSelect({
  areas,
  value,
  onChange,
}: {
  areas: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <label className="field">
      Service area
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {areas.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
    </label>
  );
}
export function Warnings({ warnings }: { warnings: string[] }) {
  return (
    warnings.length > 0 && (
      <ul className="warnings">
        {warnings.map((w) => (
          <li key={w}>{w.replaceAll('_', ' ').replace(':', ': ')}</li>
        ))}
      </ul>
    )
  );
}
export function PageHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p className="muted">{children}</p>
    </div>
  );
}
