import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compareAreas } from '../api/client';
import { AreaSelection } from '../components/AreaSelection';
import { ScoreResults } from '../components/ScoreResults';
import { PageHeading, QueryState, useAreas } from '../components/shared';
export function ComparisonPage() {
  const areas = useAreas();
  const [selection, setSelection] = useState<string[] | null>(null);
  const selected = selection ?? (areas.data ?? []).slice(0, 3).map((a) => a.id);
  const comparison = useQuery({
    queryKey: ['comparison', selected],
    queryFn: ({ signal }) => compareAreas(selected, signal),
    enabled: selected.length >= 2,
  });
  return (
    <>
      <PageHeading eyebrow="SIDE BY SIDE" title="Area Comparison">
        Compare the evidence behind each candidate, with the same model and explicit assumptions.
      </PageHeading>
      <QueryState
        pending={areas.isPending}
        error={areas.error}
        empty={areas.isSuccess && !areas.data.length}
        retry={() => void areas.refetch()}
      />
      {!!areas.data?.length && (
        <>
          <AreaSelection areas={areas.data} selected={selected} onChange={setSelection} />
          {selected.length < 2 ? (
            <p className="state">Select at least two areas to compare.</p>
          ) : (
            <>
              <QueryState
                pending={comparison.isPending}
                error={comparison.error}
                retry={() => void comparison.refetch()}
              />
              {comparison.data && (
                <>
                  <p className="small muted">
                    Model: {comparison.data.scoring_model.name}{' '}
                    {comparison.data.scoring_model.version}. Metrics use fixed normalization ranges.
                    Higher normalized values are favored by the baseline assumptions.
                  </p>
                  <ScoreResults areas={comparison.data.areas} />
                </>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
