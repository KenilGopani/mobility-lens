import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { MapPage } from '../src/pages/MapPage';
import { getCells } from '../src/api/client';
vi.mock('../src/features/map/AreaMap', () => ({
  AreaMap: ({ onViewport }: { onViewport: (bbox: number[]) => void }) => (
    <button onClick={() => onViewport([-122.2, 37.5, -122.1, 37.6])}>Pan map</button>
  ),
}));
vi.mock('../src/api/client', () => ({
  getAreas: vi.fn(async () => [{ id: 'a', name: 'San Jose', source: 'census' }]),
  getDetail: vi.fn(async () => ({
    id: 'a',
    name: 'San Jose',
    bbox: [-122.3, 37.4, -122, 37.8],
    boundary: { type: 'MultiPolygon', coordinates: [] },
  })),
  getMetrics: vi.fn(async () => ({
    analyzed_at: null,
    run: { id: 'run-a' },
    metrics: [
      {
        key: 'road_density',
        description: 'Road length per area',
        unit: 'km/km²',
        normalization_method: 'minmax_fixed',
        version: 'v1',
        ref_min: 0,
        ref_max: 25,
        higher_is_better: true,
      },
    ],
  })),
  getCells: vi.fn(async (_id, metric) => ({
    type: 'FeatureCollection',
    metric,
    limit: 2000,
    truncated: true,
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [] },
        properties: {
          h3_index: 'h3-cell-a',
          score: metric === 'overall_score' ? 0 : null,
          raw_value: metric === 'road_density' ? 12 : null,
          normalized_value: 0.48,
          confidence: 0.4,
          overlap_ratio: 1,
        },
      },
    ],
  })),
}));
it('loads bounded cells, switches metrics, exposes cell details and handles truncated results', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <MapPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole('cell', { name: '0' })).toBeInTheDocument();
  expect(screen.getByText(/Zoom in to inspect/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'h3-cell-a' }));
  expect(screen.getByRole('heading', { name: 'h3-cell-a' })).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', { name: 'Map metric' }), {
    target: { value: 'road_density' },
  });
  expect(await screen.findByRole('cell', { name: '12' })).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: 'Pan map' }));
  await waitFor(() =>
    expect(getCells).toHaveBeenLastCalledWith(
      'a',
      'road_density',
      [-122.2, 37.5, -122.1, 37.6],
      expect.anything(),
    ),
  );
  expect(screen.getByText('Road length per area')).toBeInTheDocument();
});
