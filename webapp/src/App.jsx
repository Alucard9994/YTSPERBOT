import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { enabledModules } from './config/modules.js';
import Sidebar from './components/Sidebar.jsx';

// Lazy-load all page modules
const PAGE_MAP = {
  dashboard:  lazy(() => import('./modules/dashboard/DashboardPage.jsx')),
  youtube:    lazy(() => import('./modules/youtube/YouTubePage.jsx')),
  social:     lazy(() => import('./modules/social/SocialPage.jsx')),
  trends:     lazy(() => import('./modules/trends/TrendsPage.jsx')),
  pinterest:  lazy(() => import('./modules/pinterest/PinterestPage.jsx')),
  news:       lazy(() => import('./modules/news/NewsPage.jsx')),
  config:     lazy(() => import('./modules/config_page/ConfigPage.jsx')),
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Loading() {
  return <div style={{ padding: '2rem', color: 'var(--text-muted)' }}>Caricamento…</div>;
}

export default function App() {
  const modules = enabledModules();

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-layout">
          <Sidebar />
          <div className="main-area">
            <Suspense fallback={<Loading />}>
              <Routes>
                {modules.map((mod) => {
                  const Page = PAGE_MAP[mod.id];
                  if (!Page) return null;
                  return (
                    <Route key={mod.id} path={mod.path} element={<Page />} />
                  );
                })}
                {/* Fallback: redirect to dashboard */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
