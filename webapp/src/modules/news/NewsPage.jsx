import { useQuery } from '@tanstack/react-query';
import { fetchNewsAlerts, fetchNewsKeywordCounts } from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';

// ── tooltips ──────────────────────────────────────────────────────────────────

const VELOCITY_TOOLTIP =
  'Velocity = variazione % delle menzioni nelle news rispetto al periodo precedente. ' +
  'Registrata solo quando supera la soglia (≥200%) e viene inviato un alert Telegram. ' +
  'Se "—" non è stato triggerato nessun alert recente per quella keyword.';

// ── helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(String(dateStr).replace(' ', 'T'));
  if (isNaN(d)) return '—';
  const min = Math.floor((Date.now() - d.getTime()) / 60_000);
  if (min < 1)  return 'adesso';
  if (min < 60) return `${min}m fa`;
  const h = Math.floor(min / 60);
  if (h < 24)   return `${h}h fa`;
  return `${Math.floor(h / 24)}g fa`;
}

function velColor(pct) {
  if (pct == null) return 'var(--text-dim)';
  if (pct >= 300)  return 'var(--accent)';
  if (pct >= 200)  return 'var(--orange)';
  if (pct >= 100)  return 'var(--yellow)';
  return 'var(--green)';
}
function velBg(pct) {
  if (pct == null) return 'rgba(120,120,140,.12)';
  if (pct >= 300)  return 'rgba(233,69,96,.18)';
  if (pct >= 200)  return 'rgba(249,115,22,.18)';
  if (pct >= 100)  return 'rgba(234,179,8,.18)';
  return 'rgba(34,197,94,.18)';
}

// ── sub-components ────────────────────────────────────────────────────────────

function KpiCard({ icon, label, value, sub, tooltip }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-label">
        {label}
        {tooltip && <InfoTooltip text={tooltip} />}
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function VelPill({ pct }) {
  if (pct == null) return <span className="muted">—</span>;
  return (
    <span className="vel-pill" style={{ color: velColor(pct), background: velBg(pct) }}>
      +{Math.round(pct)}%
    </span>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function NewsPage() {
  const { data: newsAlerts = [], isLoading: loadingNA } = useQuery({
    queryKey: ['news-alerts', 48],
    queryFn: () => fetchNewsAlerts(48),
    staleTime: 5 * 60_000,
  });

  const { data: newsCounts = [], isLoading: loadingNC } = useQuery({
    queryKey: ['news-counts', 48],
    queryFn: () => fetchNewsKeywordCounts(48),
    staleTime: 5 * 60_000,
  });

  // Build highest-velocity-per-keyword map
  const velMap = {};
  for (const a of newsAlerts) {
    if (!velMap[a.keyword] || (a.velocity_pct ?? 0) > (velMap[a.keyword] ?? 0))
      velMap[a.keyword] = a.velocity_pct;
  }

  const breakouts = newsAlerts.filter(a => (a.velocity_pct ?? 0) >= 300).length;

  return (
    <div className="page-wrapper">
      <Topbar title="📰 News" subtitle="Articoli di notizie per keyword monitorate" />

      {/* ── KPIs ── */}
      <div className="kpi-grid-3" style={{ marginBottom: 24 }}>
        <KpiCard
          icon="📰"
          label="NEWS MONITORATE"
          value={newsCounts.length}
          sub="Keywords rilevate (48h)"
        />
        <KpiCard
          icon="⚡"
          label="ALERT NEWS"
          value={newsAlerts.length}
          sub="Ultime 48 ore"
          tooltip={VELOCITY_TOOLTIP}
        />
        <KpiCard
          icon="🔥"
          label="BREAKOUT NEWS"
          value={breakouts}
          sub="Velocity ≥300%"
        />
      </div>

      {/* ── Keyword velocity table ── */}
      <div className="card">
        <div className="trends-card-title">
          📰 NEWS DETECTOR — KEYWORD VELOCITY (48H)
          <InfoTooltip text={VELOCITY_TOOLTIP} />
        </div>
        {loadingNC ? (
          <p className="muted">Caricamento…</p>
        ) : newsCounts.length === 0 ? (
          <EmptyState icon="📰" message="Nessuna keyword rilevata nelle news (48h)." />
        ) : (
          <table className="kw-rank-table">
            <thead>
              <tr>
                <th>KEYWORD</th>
                <th>MENZIONI (48H)</th>
                <th>VELOCITY <InfoTooltip text={VELOCITY_TOOLTIP} /></th>
                <th>ULTIMA MENZIONE</th>
              </tr>
            </thead>
            <tbody>
              {newsCounts.map(kw => (
                <tr
                  key={kw.keyword}
                  className="kw-rank-row link-item"
                  onClick={() => window.open(`https://news.google.com/search?q=${encodeURIComponent(kw.keyword)}`, '_blank')}
                >
                  <td><span className="kw-rank-name link-title">{kw.keyword}</span></td>
                  <td><span className="kw-rank-mentions">{(kw.total ?? 0).toLocaleString('it-IT')}</span></td>
                  <td><VelPill pct={velMap[kw.keyword] ?? null} /></td>
                  <td><span className="muted" style={{ fontSize: 12 }}>{timeAgo(kw.last_seen)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Recent alerts ── */}
      {newsAlerts.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="trends-card-title">🚨 ALERT RECENTI (48H)</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {newsAlerts.map((a, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px',
                borderBottom: i < newsAlerts.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1 }}>
                  {a.keyword}
                </span>
                <VelPill pct={a.velocity_pct} />
                <span style={{ fontSize: 11, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                  {timeAgo(a.sent_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
