import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPinterestTrends,
  fetchPinterestPins,
  fetchPinterestDomains,
  fetchSystemStatus,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtK(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(String(dateStr).replace(' ', 'T'));
  if (isNaN(d)) return '—';
  const min = Math.floor((Date.now() - d.getTime()) / 60_000);
  if (min < 1)   return 'adesso';
  if (min < 60)  return `${min}m fa`;
  const h = Math.floor(min / 60);
  if (h < 24)    return `${h}h fa`;
  return `${Math.floor(h / 24)}g fa`;
}

/** Best-effort category from keyword content */
const CAT_RULES = [
  ['travel',        'Travel'],
  ['haunted place', 'Travel/Horror'],
  ['house',         'Home/Horror'],
  ['decor',         'Home/Horror'],
  ['art',           'Art/History'],
  ['folklore',      'Art/History'],
  ['history',       'History'],
  ['occult',        'History'],
  ['symbol',        'History'],
  ['ancient',       'History'],
  ['dark academia', 'Entertainment'],
  ['true crime',    'Entertainment'],
  ['horror',        'Entertainment'],
  ['ghost',         'Horror'],
  ['witch',         'Spirituality'],
  ['magic',         'Spirituality'],
  ['ritual',        'Spirituality'],
  ['cryptid',       'Art/History'],
  ['paranormal',    'Horror'],
  ['mystery',       'Entertainment'],
  ['gothic',        'Entertainment'],
];

function inferCategory(keyword) {
  const k = (keyword || '').toLowerCase();
  for (const [pattern, cat] of CAT_RULES) {
    if (k.includes(pattern)) return cat;
  }
  return 'Lifestyle';
}

function growthPillStyle(type) {
  return type === 'emerging'
    ? { bg: 'rgba(233,69,96,.22)', color: 'var(--accent)', border: '1px solid rgba(233,69,96,.3)' }
    : { bg: 'rgba(34,197,94,.2)',  color: 'var(--green)',  border: '1px solid rgba(34,197,94,.3)' };
}

// ── sub-components ────────────────────────────────────────────────────────────

function KpiCard({ icon, label, value, sub }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function TrendTypeBadge({ type }) {
  const isEmerging = type === 'emerging';
  return (
    <span className={`pin-type-badge ${isEmerging ? 'pin-badge-emerging' : 'pin-badge-growing'}`}>
      {isEmerging ? 'Emerging' : 'Growing'}
    </span>
  );
}

function GrowthPill({ pct, type }) {
  const s = growthPillStyle(type);
  return (
    <span className="pin-growth-pill" style={{ background: s.bg, color: s.color, border: s.border }}>
      +{Math.round(pct)}%
    </span>
  );
}

function TrendCardRow({ item }) {
  const cat = inferCategory(item.keyword);
  const url = `https://www.pinterest.com/search/pins/?q=${encodeURIComponent(item.keyword)}`;
  return (
    <div className="pin-trend-row link-item" onClick={() => window.open(url, '_blank')}>
      <div className="pin-trend-row-body">
        <div className="pin-trend-kw link-title">{item.keyword}</div>
        <div className="pin-trend-meta">
          {cat} · {fmtK(item.saves)} saves/settimana
        </div>
      </div>
      <GrowthPill pct={item.growth_pct} type={item.trend_type} />
    </div>
  );
}

function TableRow({ item }) {
  const cat = inferCategory(item.keyword);
  const url = `https://www.pinterest.com/search/pins/?q=${encodeURIComponent(item.keyword)}`;
  return (
    <tr className="kw-rank-row link-item" onClick={() => window.open(url, '_blank')}>
      <td><span className="kw-rank-name link-title">{item.keyword}</span></td>
      <td><TrendTypeBadge type={item.trend_type} /></td>
      <td><span className="muted">{cat}</span></td>
      <td>
        <span style={{ fontWeight: 700, color: item.trend_type === 'emerging' ? 'var(--accent)' : 'var(--green)' }}>
          +{Math.round(item.growth_pct)}%
        </span>
      </td>
      <td><span className="kw-rank-mentions">{fmtK(item.saves)}</span></td>
    </tr>
  );
}

function PinCard({ pin }) {
  const repins = pin.repins ?? 0;
  const displayTitle = pin.title || pin.domain || (pin.keyword ? '#' + pin.keyword : '') || '(pin senza titolo)';
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          minWidth: 52, textAlign: 'center', borderRadius: 8, padding: '6px 4px',
          background: 'rgba(120,120,140,.10)',
        }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: repins >= 100 ? 'var(--accent)' : 'var(--text)' }}>
            {fmtK(repins)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>saves</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.4, marginBottom: 4,
            overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {pin.url
              ? <a href={pin.url} target="_blank" rel="noopener noreferrer"
                   style={{ color: 'inherit', textDecoration: 'none' }}
                   onMouseEnter={e => e.target.style.color = 'var(--accent)'}
                   onMouseLeave={e => e.target.style.color = 'inherit'}>
                  <span>{displayTitle}</span>
                </a>
              : <span>{displayTitle}</span>}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {pin.keyword && (
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', background: 'rgba(233,69,96,.12)', borderRadius: 4, padding: '2px 6px' }}>
                #{pin.keyword}
              </span>
            )}
            {pin.creator_username && (
              <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>by {pin.creator_username}</span>
            )}
            {pin.domain && (
              <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>🔗 {pin.domain}</span>
            )}
            <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 'auto' }}>
              {timeAgo(pin.scraped_at)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DomainRow({ domain, i, max }) {
  const pct = max > 0 ? Math.round((domain.total_repins / max) * 100) : 0;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 16px', borderBottom: '1px solid var(--border)',
    }}>
      <span style={{ fontSize: 13, color: 'var(--text-dim)', minWidth: 20, fontWeight: 600 }}>{i + 1}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', minWidth: 160 }}>{domain.domain}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', borderRadius: 3, background: 'var(--accent)', width: `${pct}%` }} />
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-dim)', minWidth: 60, textAlign: 'right' }}>
        {domain.pin_count} pin
      </span>
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', minWidth: 50, textAlign: 'right' }}>
        {fmtK(domain.total_repins)} saves
      </span>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

const TABS = ['Trends', 'Top Pin', 'Domini'];

export default function PinterestPage() {
  const [tab, setTab] = useState('Trends');

  const { data: trends = [], isLoading: loadTrends } = useQuery({
    queryKey: ['pinterest-trends'],
    queryFn: () => fetchPinterestTrends(168),
    staleTime: 10 * 60_000,
  });
  const { data: pins = [], isLoading: loadPins } = useQuery({
    queryKey: ['pinterest-pins'],
    queryFn: () => fetchPinterestPins(168, 30),
    staleTime: 10 * 60_000,
  });
  const { data: domains = [], isLoading: loadDomains } = useQuery({
    queryKey: ['pinterest-domains'],
    queryFn: () => fetchPinterestDomains(168, 15),
    staleTime: 10 * 60_000,
  });
  const { data: sysStatus } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const isLoading = loadTrends || loadPins || loadDomains;
  const pinterestActive = sysStatus?.credentials?.pinterest ?? true;
  const growing  = trends.filter(t => t.trend_type === 'growing');
  const emerging = trends.filter(t => t.trend_type === 'emerging');
  const avgGrowth = trends.length
    ? Math.round(trends.reduce((s, t) => s + t.growth_pct, 0) / trends.length)
    : 0;

  const maxDomainRepins = domains[0]?.total_repins || 1;

  return (
    <>
      <Topbar title="📌 Pinterest" subtitle="Trends, top pin, domini più condivisi" />
      <main className="page-content">

      {/* ── KPIs ── */}
      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        <KpiCard icon="📈" label="Trends in crescita" value={growing.length} sub="Growing (7g)" />
        <KpiCard icon="🌱" label="Trends emergenti"  value={emerging.length} sub="Emerging (nuovi)" />
        <KpiCard icon="📌" label="Pin salvati"        value={pins.length} sub="ultimi 7 giorni" />
        <KpiCard icon="🔗" label="Domini tracciati"   value={domains.length} sub={trends.length ? `avg +${avgGrowth}%` : '—'} />
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 700 : 500,
              color: tab === t ? 'var(--accent)' : 'var(--text-dim)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}>
            {t === 'Trends' ? `Trends (${trends.length})` : t === 'Top Pin' ? `Top Pin (${pins.length})` : `Domini (${domains.length})`}
          </button>
        ))}
        {isLoading && <span style={{ fontSize: 12, color: 'var(--text-dim)', alignSelf: 'center', marginLeft: 8 }}>Caricamento…</span>}
      </div>

      {/* ── Tab: Trends ── */}
      {tab === 'Trends' && (
        trends.length === 0 ? (
          <EmptyState icon="📌" message={
            pinterestActive
              ? 'Nessun trend Pinterest rilevato.'
              : 'Il modulo si attiva con APIFY_API_KEY + pinterest.use_apify: true.'
          } />
        ) : (
          <>
            <div className="pin-trends-grid">
              <div className="card">
                <div className="trends-card-title">📈 GROWING TRENDS</div>
                {growing.length === 0
                  ? <p className="muted" style={{ fontSize: 13 }}>Nessun trend in crescita.</p>
                  : growing.map(t => <TrendCardRow key={t.keyword} item={t} />)}
              </div>
              <div className="card">
                <div className="trends-card-title">🌱 EMERGING TRENDS</div>
                {emerging.length === 0
                  ? <p className="muted" style={{ fontSize: 13 }}>Nessun trend emergente.</p>
                  : emerging.map(t => <TrendCardRow key={t.keyword} item={t} />)}
              </div>
            </div>
            <div style={{ marginTop: 24 }}>
              <h2 className="section-heading">Keyword monitorate su Pinterest</h2>
              <div className="card">
                <table className="kw-rank-table">
                  <thead>
                    <tr>
                      <th>KEYWORD</th><th>TIPO</th><th>CATEGORIA</th><th>CRESCITA</th><th>SAVES</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trends.map(t => <TableRow key={t.keyword} item={t} />)}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )
      )}

      {/* ── Tab: Top Pin ── */}
      {tab === 'Top Pin' && (
        pins.length === 0
          ? <EmptyState icon="📌" message="Nessun pin salvato nel periodo. I pin vengono salvati ad ogni run del detector Pinterest." />
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {pins.map((p, i) => <PinCard key={p.pin_hash || i} pin={p} />)}
            </div>
      )}

      {/* ── Tab: Domini ── */}
      {tab === 'Domini' && (
        domains.length === 0
          ? <EmptyState icon="🔗" message="Nessun dominio esterno tracciato ancora. Appariranno dopo la prossima run del detector Pinterest." />
          : <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-dim)' }}>
                Siti web più condivisi su Pinterest nella nicchia monitorata (ultimi 7 giorni)
              </div>
              {domains.map((d, i) => (
                <DomainRow key={d.domain} domain={d} i={i} max={maxDomainRepins} />
              ))}
            </div>
      )}
    </main>
    </>
  );
}
