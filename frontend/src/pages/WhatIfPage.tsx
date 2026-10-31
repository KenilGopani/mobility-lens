import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getModels, previewScores } from '../api/client';
import { AreaSelection } from '../components/AreaSelection';
import { ScoreResults } from '../components/ScoreResults';
import { metricName, number, PageHeading, QueryState, useAreas } from '../components/shared';
import { redistribute } from '../features/scoring/weights';
function useDebounced<T>(value: T) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), 300);
    return () => clearTimeout(timer);
  }, [value]);
  return settled;
}
export function WhatIfPage() {
  const areas = useAreas();
  const models = useQuery({
    queryKey: ['scoring-models'],
    queryFn: ({ signal }) => getModels(signal),
  });
  const model = models.data?.items.find((m) => m.is_default);
  const defaults = useMemo(() => model?.weights ?? {}, [model]);
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const weights = draft ?? defaults;
  const settled = useDebounced(weights);
  const updating = settled !== weights;
  const [selection, setSelection] = useState<string[] | null>(null);
  const selected = selection ?? (areas.data ?? []).slice(0, 3).map((a) => a.id);
  const preview = useQuery({
    queryKey: ['preview', selected, settled],
    queryFn: ({ signal }) => previewScores(selected, settled, signal),
    enabled: !!model && !!selected.length && Object.keys(settled).length > 0 && !updating,
  });
  return (
    <>
      <PageHeading eyebrow="CHALLENGE THE ASSUMPTIONS" title="What-if Analysis">
        Adjust what matters. See how temporary weights change the ranking.
      </PageHeading>
      <QueryState
        pending={areas.isPending || models.isPending}
        error={areas.error ?? models.error}
        empty={areas.isSuccess && !areas.data.length}
        retry={() => {
          void areas.refetch();
          void models.refetch();
        }}
      />
      {models.isSuccess && !model && (
        <p className="state">
          No default scoring model configured. Seed a baseline model from the backend CLI.
        </p>
      )}
      {model && !!areas.data?.length && (
        <>
          <div className="panel-heading">
            <span className="badge warning">TEMPORARY ASSUMPTIONS · NOT SAVED</span>
            <button onClick={() => setDraft(null)}>Restore default model</button>
          </div>
          <AreaSelection
            minimum={1}
            areas={areas.data}
            selected={selected}
            onChange={setSelection}
          />
          <div className="two-columns">
            <article className="panel">
              <div className="panel-heading">
                <h3>Scoring weights</h3>
                <span className="badge neutral">
                  Total {number(Object.values(weights).reduce((a, b) => a + b, 0) * 100, 2)}%
                </span>
              </div>
              <p className="small muted">
                Moving one slider redistributes the other weights proportionally. The total remains
                100%.
              </p>
              {Object.entries(weights).map(([key, value]) => (
                <div className="slider-row" key={key}>
                  <label htmlFor={`weight-${key}`}>
                    {metricName(key)}
                    <strong>{number(value * 100, 2)}%</strong>
                  </label>
                  <input
                    id={`weight-${key}`}
                    aria-label={metricName(key)}
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={value * 100}
                    aria-valuetext={`${number(value * 100, 2)} percent`}
                    onChange={(e) => setDraft(redistribute(weights, key, Number(e.target.value)))}
                  />
                </div>
              ))}
            </article>
            <article className="recommendation">
              <p className="eyebrow">ONE MODEL. YOUR PRIORITIES.</p>
              <h3>Make the tradeoffs visible.</h3>
              <p>
                These weights are exploratory assumptions. Scores are recalculated by the same
                backend scoring engine, using stored normalized metrics.
              </p>
              <p>
                Missing data still lowers confidence. Adjusting priorities does not improve the
                underlying evidence.
              </p>
              <span className="badge">
                Default: {model.name} {model.version}
              </span>
            </article>
          </div>
          {!selected.length ? (
            <p className="state">Select at least one area to preview.</p>
          ) : (
            <>
              {updating || preview.isFetching ? (
                <p className="state" role="status">
                  Updating temporary scores…
                </p>
              ) : (
                <>
                  <QueryState
                    pending={preview.isPending}
                    error={preview.error}
                    retry={() => void preview.refetch()}
                  />
                  {preview.data && <ScoreResults areas={preview.data.areas} />}
                </>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
