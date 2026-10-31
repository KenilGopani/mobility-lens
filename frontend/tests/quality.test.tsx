import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { QualityPage } from '../src/pages/QualityPage';
vi.mock('../src/api/client', () => ({
  getAreas: vi.fn(async () => [{ id: 'a', name: 'Foster City', source: 'census-cb-2023' }]),
  getQuality: vi.fn(async () => ({
    run: { id: 'run-a', pipeline_version: 'v1', status: 'succeeded' },
    analyzed_at: null,
    source: { source: 'overpass' },
    finding_counts: { critical: 1, warning: 1, info: 0 },
    findings: [
      {
        rule_key: 'DQ-001',
        severity: 'critical',
        message: 'Road density is missing',
        affected_fraction: 0.2,
      },
      {
        rule_key: 'DQ-002',
        severity: 'warning',
        message: 'Tags need review',
        affected_fraction: null,
      },
    ],
    completeness: {
      cells_count: 0,
      low_confidence_cells: 0,
      low_confidence_share: null,
      low_confidence_threshold: 0.5,
      metrics: [{ metric: 'road_density', null_cells: 0, null_share: null }],
    },
  })),
}));
it('shows provenance and unavailable shares, and filters findings by severity', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <QualityPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('Road density is missing')).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  expect(screen.getByText(/census-cb-2023/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', { name: 'Severity' }), {
    target: { value: 'critical' },
  });
  expect(screen.queryByText('Tags need review')).not.toBeInTheDocument();
  expect(screen.getByText('Road density is missing')).toBeInTheDocument();
});
