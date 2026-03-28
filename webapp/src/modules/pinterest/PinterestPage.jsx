import { useQuery } from '@tanstack/react-query';
import { fetchPinterestAlerts, fetchPinterestKeywordCounts } from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';

export default function PinterestPage() {
  const { data: alerts = [], isLoading: loadingA } = useQuery({
    queryKey: ['pinterest-alerts'],
    queryFn: () => fetchPinterestAlerts(72),
    staleTime: 5 * 60_000,
  });

  const { data: counts = [], isLoading: loadingC } = useQuery({
    queryKey: ['pinterest-counts'],
    queryFn: () => fetchPinterestKeywordCounts(72),
    staleTime: 5 * 60_000,
  });

  return (
    <>
      <Topbar title="Pinterest" />
      <main className="page-content">

        {/* Keyword counts */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Menzioni keyword (72h)</h2>
          </div>
          {loadingC ? (
            <p className="muted">Caricamento…</p>
          ) : counts.length === 0 ? (
            <EmptyState icon="📌" message="Nessuna menzione Pinterest rilevata nelle ultime 72 ore." />
          ) : (
            <div className="tag-list">
              {counts.map((kw) => (
                <span key={kw.keyword} className="tag">
                  {kw.keyword} <span className="tag-count">{kw.count}</span>
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Alerts */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Alert Pinterest (72h)</h2>
          </div>
          {loadingA ? (
            <p className="muted">Caricamento…</p>
          ) : alerts.length === 0 ? (
            <EmptyState icon="🔔" message="Nessun alert Pinterest nelle ultime 72 ore." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th>Velocity</th>
                  <th>Rilevato</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td><strong>{a.keyword}</strong></td>
                    <td>
                      {a.velocity_pct != null
                        ? `+${Math.round(a.velocity_pct)}%`
                        : <span className="muted">—</span>}
                    </td>
                    <td className="muted">{new Date(a.sent_at).toLocaleString('it-IT')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

      </main>
    </>
  );
}
