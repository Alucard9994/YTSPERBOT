import { useQuery } from '@tanstack/react-query';
import { fetchAlerts, fetchConvergences, fetchKeywords } from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import StatCard from '../../components/StatCard.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import Badge from '../../components/Badge.jsx';
import { fmtDate } from '../../utils/date.js';

const VELOCITY_TOOLTIP =
  'Velocity = variazione percentuale delle menzioni di una keyword nelle ultime ore rispetto al periodo precedente. Più alta, più la keyword sta crescendo rapidamente.';
const CONV_TOOLTIP =
  'Convergenza = la stessa keyword appare in forte crescita su più piattaforme contemporaneamente (es. Reddit + Google Trends + News). Segnale molto affidabile.';

function priorityVariant(p) {
  if (p >= 8) return 'high';
  if (p >= 5) return 'medium';
  return 'low';
}

function priorityLabel(p) {
  if (p >= 8) return 'ALTA';
  if (p >= 5) return 'MEDIA';
  return 'BASSA';
}

export default function DashboardPage() {
  const { data: alerts = [], isLoading: loadingAlerts } = useQuery({
    queryKey: ['alerts', 48],
    queryFn: () => fetchAlerts(48, 30),
    staleTime: 2 * 60_000,
  });

  const { data: convergences = [], isLoading: loadingConv } = useQuery({
    queryKey: ['convergences', 48],
    queryFn: () => fetchConvergences(48),
    staleTime: 2 * 60_000,
  });

  const { data: keywords = [], isLoading: loadingKw } = useQuery({
    queryKey: ['keywords', 48],
    queryFn: () => fetchKeywords(48),
    staleTime: 2 * 60_000,
  });

  // API returns `total_mentions`; sort descending
  const topKeywords = [...keywords]
    .sort((a, b) => (b.total_mentions ?? 0) - (a.total_mentions ?? 0))
    .slice(0, 5);
  const highPriorityAlerts = alerts.filter((a) => (a.priority ?? 5) >= 7);

  return (
    <>
      <Topbar title="Dashboard" />
      <main className="page-content">

        {/* KPI strip */}
        <div className="stats-grid">
          <StatCard label="Alert (48h)" value={alerts.length} accent="var(--accent)" />
          <StatCard label="Alta priorità" value={highPriorityAlerts.length} accent="var(--danger)" />
          <StatCard label="Convergenze" value={convergences.length} accent="var(--success)" />
          <StatCard label="Keyword attive" value={keywords.length} />
        </div>

        {/* Top keywords */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Keyword più menzionate (48h)</h2>
          </div>
          {loadingKw ? (
            <p className="muted">Caricamento…</p>
          ) : topKeywords.length === 0 ? (
            <EmptyState message="Nessuna keyword registrata nelle ultime 48 ore." />
          ) : (
            <div className="tag-list">
              {topKeywords.map((kw) => (
                <span key={kw.keyword} className="tag">
                  {kw.keyword} <span className="tag-count">{kw.total_mentions}</span>
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Convergences */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">
              Convergenze multi-piattaforma{' '}
              <InfoTooltip text={CONV_TOOLTIP} />
            </h2>
          </div>
          {loadingConv ? (
            <p className="muted">Caricamento…</p>
          ) : convergences.length === 0 ? (
            <EmptyState icon="🔗" message="Nessuna convergenza rilevata nelle ultime 48 ore." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th>Piattaforme</th>
                  <th>Segnali</th>
                  <th>Rilevata</th>
                </tr>
              </thead>
              <tbody>
                {convergences.map((c) => {
                  // API returns `sources` (comma-separated), not `sources_list`
                  const srcs = (c.sources ?? '').split(',').filter(Boolean);
                  return (
                    <tr key={c.keyword}>
                      <td><strong>{c.keyword}</strong></td>
                      <td>
                        {srcs.map((s) => (
                          <span key={s} className="tag" style={{ marginRight: 4 }}>{s}</span>
                        ))}
                      </td>
                      <td>{srcs.length}</td>
                      <td className="muted">{fmtDate(c.last_seen)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        {/* Recent alerts */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">
              Alert recenti{' '}
              <InfoTooltip text={VELOCITY_TOOLTIP} />
            </h2>
          </div>
          {loadingAlerts ? (
            <p className="muted">Caricamento…</p>
          ) : alerts.length === 0 ? (
            <EmptyState message="Nessun alert nelle ultime 48 ore." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Keyword</th>
                  <th>Fonte</th>
                  <th>Velocity</th>
                  <th>Priorità</th>
                  <th>Orario</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td><span className="tag">{a.alert_type}</span></td>
                    <td><strong>{a.keyword}</strong></td>
                    <td className="muted">{a.source}</td>
                    <td>
                      {a.velocity_pct != null
                        ? `+${Math.round(a.velocity_pct)}%`
                        : <span className="muted">—</span>}
                    </td>
                    <td>
                      <Badge variant={priorityVariant(a.priority ?? 5)}>
                        {priorityLabel(a.priority ?? 5)}
                      </Badge>
                    </td>
                    <td className="muted">{fmtDate(a.sent_at)}</td>
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
