import { useQuery } from '@tanstack/react-query';
import { fetchPinterestTrends, fetchSystemStatus } from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtK(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

/** Best-effort category from keyword content */
const CAT_RULES = [
  ['travel',         'Travel'],
  ['haunted place',  'Travel/Horror'],
  ['house',          'Home/Horror'],
  ['decor',          'Home/Horror'],
  ['art',            'Art/History'],
  ['folklore',       'Art/History'],
  ['folklore',       'Art/History'],
  ['history',        'History'],
  ['occult',         'History'],
  ['symbol',         'History'],
  ['ancient',        'History'],
  ['dark academia',  'Entertainment'],
  ['true crime',     'Entertainment'],
  ['horror',         'Entertainment'],
  ['ghost',          'Horror'],
  ['witch',          'Spirituality'],
  ['magic',          'Spirituality'],
  ['ritual',         'Spirituality'],
  ['cryptid',        'Art/History'],
  ['paranormal',     'Horror'],
  ['mystery',        'Entertainment'],
  ['gothic',         'Entertainment'],
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

/** Card item inside GROWING or EMERGING card */
function TrendCardRow({ item }) {
  const cat = inferCategory(item.keyword);
  const url = `https://www.pinterest.com/search/pins/?q=${encodeURIComponent(item.keyword)}`;
  return (
    <div className="pin-trend-row link-item" onClick={() => window.open(url, '_blank')}>
      <div className="pin-trend-row-body">
        <div className="pin-trend-kw link-title">{item.keyword}</div>
        <div className="pin-trend-meta">
          {cat} · {item.regions} · {fmtK(item.saves)} saves/settimana
        </div>
      </div>
      <GrowthPill pct={item.growth_pct} type={item.trend_type} />
    </div>
  );
}

/** Full keyword table row */
function TableRow({ item, i }) {
  const cat = inferCategory(item.keyword);
  const url = `https://www.pinterest.com/search/pins/?q=${encodeURIComponent(item.keyword)}`;
  return (
    <tr className="kw-rank-row link-item" onClick={() => window.open(url, '_blank')}>
      <td><span className="kw-rank-name link-title">{item.keyword}</span></td>
      <td><TrendTypeBadge type={item.trend_type} /></td>
      <td><span className="muted">{cat}</span></td>
      <td><span className="muted">{item.regions}</span></td>
      <td>
        <span style={{
          fontWeight: 700,
          color: item.trend_type === 'emerging' ? 'var(--accent)' : 'var(--green)'
        }}>
          +{Math.round(item.growth_pct)}%
        </span>
      </td>
      <td><span className="kw-rank-mentions">{fmtK(item.saves)}</span></td>
    </tr>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function PinterestPage() {
  const { data: trends = [], isLoading } = useQuery({
    queryKey: ['pinterest-trends'],
    queryFn: () => fetchPinterestTrends(168),
    staleTime: 10 * 60_000,
  });

  const { data: sysStatus } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const pinterestActive = sysStatus?.credentials?.pinterest ?? true;

  const growing  = trends.filter(t => t.trend_type === 'growing');
  const emerging = trends.filter(t => t.trend_type === 'emerging');

  // Unique regions
  const allRegions = [...new Set(trends.flatMap(t => t.regions.split(',')))].filter(Boolean);
  const regionLabel = allRegions.length > 0 ? allRegions.join(' + ') : '—';

  return (
    <>
      <Topbar title="📌 Pinterest" />
      <main className="page-content">

        {/* ── KPI row ── */}
        <div className="kpi-grid-3">
          <KpiCard
            icon="📈"
            label="TRENDS IN CRESCITA"
            value={growing.length}
            sub="Growing (settimana)"
          />
          <KpiCard
            icon="🌱"
            label="TRENDS EMERGENTI"
            value={emerging.length}
            sub="Emerging (nuovi)"
          />
          <KpiCard
            icon="🌍"
            label="REGIONI MONITORATE"
            value={allRegions.length || '—'}
            sub={regionLabel}
          />
        </div>

        {/* ── 2-column trend cards ── */}
        {isLoading ? (
          <p className="muted">Caricamento…</p>
        ) : trends.length === 0 ? (
          <EmptyState
            icon="📌"
            message={
              pinterestActive
                ? 'Nessun trend Pinterest rilevato.'
                : 'Nessun trend Pinterest rilevato. Il modulo si attiva con PINTEREST_ACCESS_TOKEN (API nativa) oppure con APIFY_API_KEY + pinterest.use_apify: true nel config.'
            }
          />
        ) : (
          <>
            <div className="pin-trends-grid">
              {/* Growing */}
              <div className="card">
                <div className="trends-card-title">📈 GROWING TRENDS</div>
                {growing.length === 0 ? (
                  <p className="muted" style={{ fontSize: 13 }}>Nessun trend in crescita.</p>
                ) : (
                  <div>
                    {growing.map(t => <TrendCardRow key={t.keyword} item={t} />)}
                  </div>
                )}
              </div>

              {/* Emerging */}
              <div className="card">
                <div className="trends-card-title">🌱 EMERGING TRENDS</div>
                {emerging.length === 0 ? (
                  <p className="muted" style={{ fontSize: 13 }}>Nessun trend emergente.</p>
                ) : (
                  <div>
                    {emerging.map(t => <TrendCardRow key={t.keyword} item={t} />)}
                  </div>
                )}
              </div>
            </div>

            {/* ── Full keyword table ── */}
            <div style={{ marginTop: 24 }}>
              <h2 className="section-heading">Keyword monitorate su Pinterest</h2>
              <div className="card">
                <table className="kw-rank-table">
                  <thead>
                    <tr>
                      <th>KEYWORD</th>
                      <th>TIPO</th>
                      <th>CATEGORIA</th>
                      <th>REGIONE</th>
                      <th>CRESCITA SETTIMANALE</th>
                      <th>SAVES</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trends.map((t, i) => <TableRow key={t.keyword} item={t} i={i} />)}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

      </main>
    </>
  );
}
