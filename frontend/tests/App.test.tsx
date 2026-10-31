import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/App';

function renderAt(path: string) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('app shell', () => {
  it('renders the product heading and primary navigation', () => {
    renderAt('/');
    expect(screen.getByRole('heading', { level: 1, name: 'MobilityLens' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/');
  });

  it('renders the overview page at /', () => {
    renderAt('/');
    expect(
      screen.getByRole('heading', { level: 2, name: 'Executive Overview' }),
    ).toBeInTheDocument();
  });

  it('shows a not-found page for unknown routes', () => {
    renderAt('/nope');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
