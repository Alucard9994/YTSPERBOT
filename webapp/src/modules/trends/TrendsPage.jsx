import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchGoogleTrends, fetchRisingQueries, fetchTrendingRss } from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import EmptyState from '../../components/EmptyState.jsx';

// ── tooltips ──────────────────────────────────────────────────────────────────

const GT_TOOLTIP =
  'Keyword monitorate su Google Trends (ultimi 7 giorni), ordinate per volume di menzioni. La barra indica il peso relativo rispetto alla keyword più cercata.';
const RISING_TOOLTIP =
  'Rising Query = query correlate a una keyword principale in forte crescita su Google. "Breakout" indica crescita >5000% (query nuova o virale).';
const TRENDING_TOOLTIP =
  'Google Trending RSS — top ricerche attuali filtrate per geo IT/US, aggiornate ogni ora.';

// ── geo flags ─────────────────────────────────────────────────────────────────

const GEO_FLAGS = {
  IT: '🇮🇹', US: '🇺🇸', GB: '🇬🇧',
  DE: '🇩🇪', FR: '🇫🇷', ES: '🇪🇸',
};

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

function VelocityRow({ item, maxTotal }) {
  const score = maxTotal > 0 ? Math.round((item.total / maxTotal) * 100) : 0;
  return (
    <div className="velocity-row">
      <div className="velocity-top">
        <span className="velocity-name">{item.keyword}</span>
        <span className="velocity-score-num">{item.total.toLocaleString('it-IT')}</span>
      </div>
      <div className="velocity-bar-wrap">
        <div className="velocity-bar" style={{ width: `${score}%` }} />
      </div>
      <div className="velocity-score-label">Interest score: {score}/100</div>
    </div>
  );
}

function RisingItem({ item }) {
  let extra = {};
  try { extra = JSON.parse(item.extra_json ?? '{}'); } catch {}
  const isBreakout = extra.breakout;
  const pct        = item.velocity_pct;

  return (
    <div className="rising-item">
      <div className="rising-name">{item.keyword}</div>
      {extra.parent_keyword && (
        <div className="rising-parent">correlata a: {extra.parent_keyword}</div>
      )}
      {isBreakout ? (
        <span className="breakout-badge">Breakout</span>
      ) : pct != null ? (
        <span className="rising-pct-badge">+{Math.round(pct)}%</span>
      ) : null}
    </div>
  );
}

function TrendingRssItem({ item, rank }) {
  let extra = {};
  try { extra = JSON.parse(item.extra_json ?? '{}'); } catch {}
  const geo     = (extra.geo ?? '').toUpperCase();
  const flag    = GEO_FLAGS[geo] ?? '🌍';
  const traffic = extra.traffic ?? null;

  return (
    <div className="trending-item">
      <div className="trending-info">
        <div className="trending-name">{item.keyword}</div>
        <div className="trending-rank">
          {traffic ? `Traffico: ${traffic}` : `Trending #${rank}`}
        </div>
      </div>
      <div className="geo-badge">
        <span style={{ fontSize: 18, lineHeight: 1 }}>{flag}</span>
        {geo && (
          <span style={{ fontSize: 9, color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '.5px' }}>
            {geo}
          </span>
        )}
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function TrendsPage() {
  const [tab, setTab] = useState('google');

  const { data: googleTrends = [], isLoading: loadingG } = useQuery({
    queryKey: ['google-trends', 168],
    queryFn: () => fetchGoogleTrends(168),
    staleTime: 5 * 60_000,
  });

  const { data: rising = [], isLoading: loadingR } = useQuery({
    queryKey: ['rising-queries'],
    queryFn: () => fetchRisingQueries(48),
    staleTime: 5 * 60_000,
  });

  const { data: trendingRss = [], isLoading: loadingT } = useQuery({
    queryKey: ['trending-rss'],
    queryFn: () => fetchTrendingRss(24),
    staleTime: 5 * 60_000,
  });

  const maxTotal = Math.max(...googleTrends.map(k => k.total), 1);

  const breakoutCount = rising.filter(r => {
    try {
      const e = JSON.parse(r.extra_json ?? '{}');
      return e.breakout || (r.velocity_pct ?? 0) >= 500;
    } catch {
      return (r.velocity_pct ?? 0) >= 500;
    }
  }).length;

  return (
    <>
      <Topbar title="📊 Trends" />
      <main className="page-content">

        {/* ── KPI strip ──────────────────────────────── */}
        <div className="kpi-grid-3">
          <KpiCard
            icon="📊"
            label="GOOGLE TRENDS ATTIVI"
            value={googleTrends.length}
            sub="Keywords in monitoring"
          />
          <KpiCard
            icon="⚡"
            label="RISING QUERIES"
            value={rising.length}
            sub={`${breakoutCount} breakout oggi`}
            tooltip={RISING_TOOLTIP}
          />
          <KpiCard
            icon="🌍"
            label="TRENDING IT/US"
            value={trendingRss.length}
            sub="Match niche nelle top 50"
            tooltip={TRENDING_TOOLTIP}
          />
        </div>

        {/* ── Tabs ───────────────────────────────────── */}
        <div className="tabs">
          {[
            { key: 'google',   label: `📊 Google Trends (${googleTrends.length})` },
            { key: 'rising',   label: `⚡ Rising Queries (${rising.length})` },
            { key: 'trending', label: `🌍 Trending RSS (${trendingRss.length})` },
          ].map(t => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Google Trends ──────────────────────────── */}
        {tab === 'google' && (
          <div className="card">
            <div className="trends-card-title">
              📊 GOOGLE TRENDS — VELOCITY KEYWORD (7 GIORNI)
              <InfoTooltip text={GT_TOOLTIP} />
            </div>
            {loadingG ? (
              <p className="muted">Caricamento…</p>
            ) : googleTrends.length === 0 ? (
              <EmptyState icon="📈" message="Nessun dato Google Trends negli ultimi 7 giorni." />
            ) : (
              googleTrends.map(kw => (
                <VelocityRow key={kw.keyword} item={kw} maxTotal={maxTotal} />
              ))
            )}
          </div>
        )}

        {/* ── Rising Queries ─────────────────────────── */}
        {tab === 'rising' && (
          <div className="card">
            <div className="trends-card-title">
              ⚡ RISING QUERIES
              <InfoTooltip text={RISING_TOOLTIP} />
            </div>
            {loadingR ? (
              <p className="muted">Caricamento…</p>
            ) : rising.length === 0 ? (
              <EmptyState icon="🚀" message="Nessuna rising query nelle ultime 48 ore." />
            ) : (
              rising.map(r => (
                <RisingItem key={r.id ?? r.keyword} item={r} />
              ))
            )}
          </div>
        )}

        {/* ── Trending IT + US ───────────────────────── */}
        {tab === 'trending' && (
          <div className="card">
            <div className="trends-card-title">
              🌍 GOOGLE TRENDING IT + US
              <InfoTooltip text={TRENDING_TOOLTIP} />
            </div>
            {loadingT ? (
              <p className="muted">Caricamento…</p>
            ) : trendingRss.length === 0 ? (
              <EmptyState icon="📡" message="Nessun trend RSS nelle ultime 24 ore." />
            ) : (
              trendingRss.map((r, i) => (
                <TrendingRssItem key={r.id ?? i} item={r} rank={i + 1} />
              ))
            )}
          </div>
        )}

      </main>
    </>
  );
}
