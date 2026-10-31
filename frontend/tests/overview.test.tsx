import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewPage } from '../src/pages/OverviewPage';

afterEach(() => vi.unstubAllGlobals());
function renderOverview() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <OverviewPage />
    </QueryClientProvider>,
  );
}
it('shows unscored areas without turning missing scores into zero', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [{ id: 'a', name: 'Foster City', score: null, rank: null, confidence: null }],
          total: 1,
        }),
      ),
    ),
  );
  renderOverview();
  expect(await screen.findByText('No scored areas yet')).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  expect(screen.getByRole('rowheader', { name: 'Foster City' })).toBeInTheDocument();
});
it('shows the API failure with a retry action', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Cannot reach analysis API')));
  renderOverview();
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach analysis API');
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
});
