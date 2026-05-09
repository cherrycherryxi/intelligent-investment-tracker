import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { LoadingSpinner } from './components/common/LoadingSpinner';
import { AppLayout } from './components/layout/AppLayout';

const TransactionsPage = lazy(() => import('./features/transactions/TransactionsPage'));
const PerformancePage = lazy(() => import('./features/performance/PerformancePage'));
const AuditPage = lazy(() => import('./features/performance/AuditPage'));
const PositionsPage = lazy(() => import('./features/positions/PositionsPage'));
const ImportsPage = lazy(() => import('./features/imports/ImportsPage'));
const AdvicePage = lazy(() => import('./features/advice/AdvicePage'));
const ExchangeRatesPage = lazy(() => import('./features/exchange-rates/ExchangeRatesPage'));
const AgentToolsPage = lazy(() => import('./features/agents/AgentToolsPage'));

export function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Suspense fallback={<LoadingSpinner message="Loading module..." />}>
          <Routes>
            <Route path="/" element={<Navigate to="/transactions" replace />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/performance" element={<PerformancePage />} />
            <Route path="/performance/audit" element={<AuditPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/imports" element={<ImportsPage />} />
            <Route path="/advice" element={<AdvicePage />} />
            <Route path="/agent-tools" element={<AgentToolsPage />} />
            <Route path="/exchange-rates" element={<ExchangeRatesPage />} />
          </Routes>
        </Suspense>
      </AppLayout>
    </BrowserRouter>
  );
}
