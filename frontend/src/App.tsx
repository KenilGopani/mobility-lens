import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import { OverviewPage } from './pages/OverviewPage';
import { ComparisonPage } from './pages/ComparisonPage';
import { QualityPage } from './pages/QualityPage';
import { WhatIfPage } from './pages/WhatIfPage';
import { MapPage } from './pages/MapPage';
import './styles.css';
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});
export function AppRoutes() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <span className="brand-mark" aria-hidden="true">
          M↗
        </span>
        <h1>MobilityLens</h1>
        <p className="sidebar-caption">EXPANSION INTELLIGENCE</p>
        <nav aria-label="Primary">
          <NavLink to="/" end>
            <span aria-hidden="true">◫</span> Overview
          </NavLink>
          <NavLink to="/comparison">
            <span aria-hidden="true">▥</span> Comparison
          </NavLink>
          <NavLink to="/quality">
            <span aria-hidden="true">◈</span> Data Quality
          </NavLink>
          <NavLink to="/what-if">
            <span aria-hidden="true">≋</span> What-if Analysis
          </NavLink>
          <NavLink to="/map">
            <span aria-hidden="true">⌖</span> Interactive Map
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <span className="status-dot" /> Public data workspace<p>Bay Area · California</p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            Workspace <span className="muted">/ Service area planning</span>
          </span>
          <span className="badge neutral">PUBLIC DATA</span>
        </header>
        <main id="main-content">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/comparison" element={<ComparisonPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/what-if" element={<WhatIfPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="*" element={<h2>Page not found</h2>} />
          </Routes>
        </main>
        <footer className="page-footer">
          OpenStreetMap contributors · Census boundaries{' '}
          <span>Transparent assumptions. Traceable decisions.</span>
        </footer>
      </div>
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
