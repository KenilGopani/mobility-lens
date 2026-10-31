import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ComparisonPage } from '../src/pages/ComparisonPage';
import { compareAreas } from '../src/api/client';
vi.mock('../src/api/client', () => ({
  getAreas: vi.fn(async () => [
    { id: 'a', name: 'Foster City' },
    { id: 'b', name: 'San Jose' },
  ]),
  compareAreas: vi.fn(async () => ({
    scoring_model: { name: 'baseline', version: 'v1' },
    areas: [
      {
        service_area_id: 'a',
        name: 'Foster City',
        score: 0,
        rank: 2,
        confidence: 0.4,
        components: [
          {
            metric: 'road_density',
            raw_value: null,
            normalized_value: null,
            contribution: null,
            effective_weight: 0,
          },
        ],
        strengths: [],
        risks: [],
        warnings: ['missing_metric:road_density'],
        run: null,
      },
    ],
  })),
}));
it('compares selected areas, preserves zero and missing values, and stops below two areas', async () => {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ComparisonPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole('columnheader', { name: 'Foster City' })).toBeInTheDocument();
  expect(screen.getByText('0')).toBeInTheDocument();
  expect(screen.getByText(/Unavailable \/ Unavailable \/ Unavailable/)).toBeInTheDocument();
  expect(screen.getByText('40% confidence')).toHaveClass('warning');
  await waitFor(() => expect(compareAreas).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('checkbox', { name: 'San Jose' }));
  expect(screen.getByText('Select at least two areas to compare.')).toBeInTheDocument();
  expect(compareAreas).toHaveBeenCalledTimes(1);
});
