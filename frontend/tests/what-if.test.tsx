import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { WhatIfPage } from '../src/pages/WhatIfPage';
import { previewScores } from '../src/api/client';
vi.mock('../src/api/client', () => ({
  getAreas: vi.fn(async () => [{ id: 'a', name: 'Foster City' }]),
  getModels: vi.fn(async () => ({
    items: [
      {
        id: 'model',
        is_default: true,
        name: 'baseline',
        version: 'v1',
        weights: { road_density: 0.5, network_directness: 0.5 },
      },
    ],
  })),
  previewScores: vi.fn(async (_ids, weights) => ({
    temporary: true,
    areas: [
      {
        service_area_id: 'a',
        name: 'Foster City',
        score: weights.road_density * 100,
        rank: 1,
        confidence: 1,
        components: [],
        strengths: [],
        risks: [],
        warnings: [],
        run: null,
      },
    ],
  })),
}));
it('sends valid temporary weights, updates scores and restores the default model', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WhatIfPage />
    </QueryClientProvider>,
  );
  const slider = await screen.findByRole('slider', { name: 'Road density' });
  await waitFor(() => expect(previewScores).toHaveBeenCalled());
  fireEvent.change(slider, { target: { value: '80' } });
  expect(screen.getByText('Updating temporary scores…')).toBeInTheDocument();
  await waitFor(() =>
    expect(previewScores).toHaveBeenLastCalledWith(
      ['a'],
      { road_density: 0.8, network_directness: 0.2 },
      expect.anything(),
    ),
  );
  expect(await screen.findByRole('cell', { name: '80' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Restore default model' }));
  await waitFor(() => expect(slider).toHaveValue('50'));
  expect(screen.getByText(/NOT SAVED/)).toBeInTheDocument();
});
