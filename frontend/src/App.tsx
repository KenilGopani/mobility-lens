import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import { OverviewPage } from './pages/OverviewPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function AppRoutes() {
  return (
    <div>
      <header>
        <h1>MobilityLens</h1>
        <nav aria-label="Primary">
          <NavLink to="/" end>
            Overview
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="*" element={<h2>Page not found</h2>} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
