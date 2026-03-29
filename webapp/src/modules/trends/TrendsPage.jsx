import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchGoogleTrends, fetchRisingQueries, fetchTrendingRss,
  fetchConfigLists, addConfigListItem, removeConfigListItem,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InlineListManager from '../../components/InlineListManager.jsx';

// ── tooltips ──────────────────────────────────────────────────────────────────

const GT_TOOLTIP =
  'Il numero a destra è il totale delle menzioni registrate su Google Trends negli ultimi 7 giorni. La barra e "Interest score" mostrano il peso relativo: 100/100 = keyword con più menzioni nel periodo, le altre sono scalate proporzionalmente. Non è un volume assoluto di ricerche Google, ma l\'intensità relativa nel set monitorato.';
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
  const url   = `https://trends.google.com/trends/explore?q=${encodeURIComponent(item.keyword)}&geo=IT`;
  return (
    <div className="velocity-row link-item" onClick={() => window.open(url, '_blank')}>
      <div className="velocity-top">
        <span className="velocity-name link-title">{item.keyword}</span>
        <span className="velocity-score-num">{item.total.toLocaleString('it-IT')}</span>
      </div>
      <div className="velocity-bar-wrap">
        <div className="velocity-bar" style={{ width: `${score}%` }} />
      </div>
      <div className="velocity-score-label">Peso relativo: {score}/100</div>
    </div>
  );
}

function RisingItem({ item }) {
  let extra = {};
  try { extra = JSON.parse(item.extra_json ?? '{}'); } catch {}
  const isBreakout = extra.breakout;
  const pct        = item.velocity_pct;
  const url        = `https://trends.google.com/trends/explore?q=${encodeURIComponent(item.keyword)}&geo=IT`;

  return (
    <div className="rising-item link-item" onClick={() => window.open(url, '_blank')}>
      <div className="rising-name link-title">{item.keyword}</div>
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
  const url     = geo
    ? `https://trends.google.com/trends/trendingsearches/daily?geo=${geo}`
    : `https://www.google.com/search?q=${encodeURIComponent(item.keyword)}`;

  return (
    <div className="trending-item link-item" onClick={() => window.open(url, '_blank')}>
      <div className="trending-info">
        <div className="trending-name link-title">{item.keyword}</div>
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
  const queryClient = useQueryClient();

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

  const { data: configLists = {} } = useQuery({
    queryKey: ['config-lists'],
    queryFn: fetchConfigLists,
    staleTime: 30_000,
  });
  const rssIt      = configLists.rss_italian  ?? [];
  const rssEn      = configLists.rss_english  ?? [];
  const gAlerts    = configLists.google_alerts ?? [];

  const addListMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });
  const removeListMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
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
          <>
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
            <div className="card" style={{ marginTop: 14 }}>
              <div className="trends-card-title" style={{ marginBottom: 10 }}>🔔 GOOGLE ALERTS MONITORATI</div>
              <InlineListManager
                listKey="google_alerts"
                items={gAlerts}
                onAdd={(lk, v) => addListMutation.mutate({ listKey: lk, value: v })}
                onRemove={(lk, v) => removeListMutation.mutate({ listKey: lk, value: v })}
                placeholder="Termine da monitorare su Google Alerts"
                isPending={addListMutation.isPending || removeListMutation.isPending}
              />
            </div>
          </>
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
          <TrendingTabContent
            trendingRss={trendingRss}
            loadingT={loadingT}
            rssIt={rssIt}
            rssEn={rssEn}
            addListMutation={addListMutation}
            removeListMutation={removeListMutation}
          />
        )}
      </main>
    </>
  );
}

function TrendingTabContent({ trendingRss, loadingT, rssIt, rssEn, addListMutation, removeListMutation }) {
  const [geoFilter, setGeoFilter] = useState('ALL');
  const geoOptions = ['ALL', ...Object.keys(GEO_FLAGS)];
  const filteredRss = geoFilter === 'ALL' ? trendingRss : trendingRss.filter(r => {
    try { return (JSON.parse(r.extra_json ?? '{}').geo ?? '').toUpperCase() === geoFilter; }
    catch { return false; }
  });
  return (
    <>
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <div className="trends-card-title" style={{ margin: 0 }}>
            🌍 GOOGLE TRENDING IT + US
            <InfoTooltip text={TRENDING_TOOLTIP} />
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {geoOptions.map(g => (
              <button
                key={g}
                className={`tab-btn${geoFilter === g ? ' active' : ''}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => setGeoFilter(g)}
              >
                {g === 'ALL' ? '🌍 Tutti' : `${GEO_FLAGS[g] ?? ''} ${g}`}
              </button>
            ))}
          </div>
        </div>
        {loadingT ? (
          <p className="muted">Caricamento…</p>
        ) : filteredRss.length === 0 ? (
          <EmptyState icon="📡" message={geoFilter === 'ALL' ? 'Nessun trend RSS nelle ultime 24 ore.' : `Nessun trend per ${geoFilter}.`} />
        ) : (
          filteredRss.map((r, i) => (
            <TrendingRssItem key={r.id ?? i} item={r} rank={i + 1} />
          ))
        )}
      </div>
            <div className="grid-2" style={{ marginTop: 14 }}>
              <div className="card">
                <div className="trends-card-title" style={{ marginBottom: 10 }}>📡 RSS FEED ITALIANI</div>
                <InlineListManager
                  listKey="rss_italian"
                  items={rssIt}
                  onAdd={(lk, v) => addListMutation.mutate({ listKey: lk, value: v })}
                  onRemove={(lk, v) => removeListMutation.mutate({ listKey: lk, value: v })}
                  placeholder="URL feed RSS"
                  isPending={addListMutation.isPending || removeListMutation.isPending}
                />
              </div>
              <div className="card">
                <div className="trends-card-title" style={{ marginBottom: 10 }}>📡 RSS FEED INGLESI</div>
                <InlineListManager
                  listKey="rss_english"
                  items={rssEn}
                  onAdd={(lk, v) => addListMutation.mutate({ listKey: lk, value: v })}
                  onRemove={(lk, v) => removeListMutation.mutate({ listKey: lk, value: v })}
                  placeholder="URL feed RSS"
                  isPending={addListMutation.isPending || removeListMutation.isPending}
                />
              </div>
            </div>
    </>
  );
}
