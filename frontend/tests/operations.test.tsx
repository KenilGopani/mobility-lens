import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { OperationsPage } from '../src/pages/OperationsPage';
vi.mock('../src/api/client', () => ({
  getAreas: vi.fn(async () => [{ id: 'a', name: 'Foster City', slug: 'foster-city' }]),
  getSimulations: vi.fn(async () => ({
    items: [{ id: 'sim', seed: 42, created_at: '2026-01-01T00:00:00Z' }],
  })),
  getOperations: vi.fn(async () => ({
    synthetic: true,
    simulation: {
      id: 'sim',
      seed: 42,
      generator_version: 'v1',
      analysis_run_id: 'source-run',
      parameters: { routes: 0 },
      simulated_start_at: '2026-01-01T00:00:00Z',
      created_at: '2026-01-01T00:00:00Z',
    },
    route_count: 0,
    completion_rate: null,
    intervention_rate: null,
    mean_trip_duration_minutes: null,
    open_issues: 0,
    resolved_issues: 0,
    mean_resolution_hours: null,
    issues_by_severity: { warning: 0 },
    days: [],
  })),
}));
it('labels scenarios as synthetic and preserves unavailable aggregate values', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <OperationsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByRole('note')).toHaveTextContent('Synthetic data · simulation only');
  expect(await screen.findByRole('heading', { name: 'Scenario provenance' })).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  expect(screen.getByText(/Pinned geospatial run source-run/)).toBeInTheDocument();
});
