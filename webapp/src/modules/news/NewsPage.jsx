import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchNewsAlerts,
  fetchNewsKeywordCounts,
  fetchTwitterAlerts,
  fetchTwitterCounts,
  fetchKeywordSources,
  fetchConfigLists,
  addConfigListItem,
  removeConfigListItem,
} from '../../api/client.js';
import InlineListManager from '../../components/InlineListManager.jsx';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';

// ── tooltips ──────────────────────────────────────────────────────────────────

const VELOCITY_TOOLTIP =
  'Velocity = variazione % delle menzioni rispetto al periodo precedente. Viene registrata solo quando il modulo rileva una soglia superata (≥200% per News, ≥100% per Twitter) e invia un alert Telegram. Se il valore è "—" non è stato triggerato nessun alert recente per quella keyword.';
const TW_ALERT_TOOLTIP =
  'Alert generati quando una keyword supera +300% di velocity su Twitter nelle ultime 48h.';
const RD_ALERT_TOOLTIP =
  'Alert Reddit generati quando la keyword supera +300% di velocity nei subreddit monitorati.';
const RD_VELOCITY_TOOLTIP =
  'Crescita % delle menzioni per keyword Reddit nelle ultime 48h. La barra mostra il peso relativo.';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtK(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.0', '') + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1).replace('.0', '') + 'K';
  return String(n ?? 0);
}

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
  if (pct == null)   return 'var(--text-dim)';
  if (pct >= 300)    return 'var(--accent)';
  if (pct >= 200)    return 'var(--orange)';
  if (pct >= 100)    return 'var(--yellow)';
  return 'var(--green)';
}
function velBg(pct) {
  if (pct == null)   return 'rgba(120,120,140,.12)';
  if (pct >= 300)    return 'rgba(233,69,96,.18)';
  if (pct >= 200)    return 'rgba(249,115,22,.18)';
  if (pct >= 100)    return 'rgba(234,179,8,.18)';
  return 'rgba(34,197,94,.18)';
}

/** Build highest-velocity-per-keyword map from an alerts array */
function buildVelMap(alerts) {
  const m = {};
  for (const a of alerts) {
    if (!m[a.keyword] || (a.velocity_pct ?? 0) > (m[a.keyword] ?? 0))
      m[a.keyword] = a.velocity_pct;
  }
  return m;
}

// ── shared sub-components ─────────────────────────────────────────────────────

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

function LastSeen({ dateStr }) {
  if (!dateStr) return <span className="muted">—</span>;
  const d = new Date(String(dateStr).replace(' ', 'T'));
  if (isNaN(d)) return <span className="muted">—</span>;
  return <span className="muted" style={{ fontSize: 12 }}>{timeAgo(dateStr)}</span>;
}

// ── News Detector tab ─────────────────────────────────────────────────────────

function NewsTab({ newsAlerts, newsCounts, loadingNA, loadingNC }) {
  const velMap     = buildVelMap(newsAlerts);
  const breakouts  = newsAlerts.filter(a => (a.velocity_pct ?? 0) >= 300).length;

  return (
    <>
      <div className="kpi-grid-3">
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
                  <td><LastSeen dateStr={kw.last_seen} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// ── Twitter/X tab ─────────────────────────────────────────────────────────────

function TwitterTab({ twitterCounts48, twitterCounts7d, twitterAlerts, loadingTC, loadingTA }) {
  const velMap      = buildVelMap(twitterAlerts);
  const totalTweets = twitterCounts7d.reduce((s, k) => s + (k.total ?? 0), 0);
  const alertHigh   = twitterAlerts.filter(a => (a.velocity_pct ?? 0) >= 300).length;

  return (
    <>
      <div className="kpi-grid-3">
        <KpiCard
          icon="🐦"
          label="TWEET MONITORATI"
          value={fmtK(totalTweets)}
          sub="Ultimi 7 giorni"
        />
        <KpiCard
          icon="🏷️"
          label="KEYWORD ATTIVE"
          value={twitterCounts48.length}
          sub="Campionate ogni 8h"
        />
        <KpiCard
          icon="⚡"
          label="ALERT TWITTER"
          value={alertHigh}
          sub="Velocity ≥300%"
          tooltip={TW_ALERT_TOOLTIP}
        />
      </div>

      <div className="card">
        <div className="trends-card-title">🐦 TWITTER/X — KEYWORD MONITOR (48H)</div>
        {loadingTC ? (
          <p className="muted">Caricamento…</p>
        ) : twitterCounts48.length === 0 ? (
          <EmptyState icon="🐦" message="Nessuna keyword Twitter nelle ultime 48 ore." />
        ) : (
          <table className="kw-rank-table">
            <thead>
              <tr>
                <th>KEYWORD</th>
                <th>TWEET (48H)</th>
                <th>VELOCITY <InfoTooltip text={VELOCITY_TOOLTIP} /></th>
                <th>ULTIMA MENZIONE</th>
              </tr>
            </thead>
            <tbody>
              {twitterCounts48.map(kw => (
                <tr
                  key={kw.keyword}
                  className="kw-rank-row link-item"
                  onClick={() => window.open(`https://twitter.com/search?q=${encodeURIComponent(kw.keyword)}`, '_blank')}
                >
                  <td><span className="kw-rank-name link-title">{kw.keyword}</span></td>
                  <td><span className="kw-rank-mentions">{(kw.total ?? 0).toLocaleString('it-IT')}</span></td>
                  <td><VelPill pct={velMap[kw.keyword] ?? null} /></td>
                  <td><LastSeen dateStr={kw.last_seen} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// ── Reddit post card (keyword-centric, since post titles are not stored in DB) ─

function RedditAlertCard({ alert: a }) {
  let extra = {};
  try { extra = JSON.parse(a.extra_json ?? '{}'); } catch {}
  const sub   = extra.subreddit ?? null;
  const flair = extra.flair ?? null;
  const pct   = a.velocity_pct;
  const subClean = sub ? sub.replace(/^r\//i, '') : null;
  const url = subClean
    ? `https://www.reddit.com/r/${subClean}/search/?q=${encodeURIComponent(a.keyword)}`
    : `https://www.reddit.com/search/?q=${encodeURIComponent(a.keyword)}`;

  return (
    <div className="reddit-post-card link-item" onClick={() => window.open(url, '_blank')}>
      <div className="reddit-post-meta">
        {sub && (
          <span className="reddit-sub-badge">r/{subClean}</span>
        )}
        {flair && (
          <span className="reddit-flair-badge">{flair}</span>
        )}
        <span className="reddit-kw-badge">🎫 {a.keyword}</span>
        <span className="reddit-time">{timeAgo(a.sent_at)}</span>
      </div>
      <div className="reddit-post-title">{a.keyword}</div>
      <div className="reddit-post-footer">
        {pct != null ? (
          <span style={{ color: velColor(pct), fontSize: 13, fontWeight: 700 }}>
            +{Math.round(pct)}% velocity
          </span>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>velocity n/d</span>
        )}
        <span className="muted" style={{ fontSize: 12, marginLeft: 'auto' }}>
          Priorità {a.priority ?? '—'}/10
        </span>
      </div>
    </div>
  );
}


function SubredditRow({ name, todayCount }) {
  const url = `https://www.reddit.com/r/${name}`;
  return (
    <div className="subreddit-item link-item" onClick={() => window.open(url, '_blank')}>
      <span className="subreddit-name link-title">r/{name}</span>
      <span className="link-icon">↗</span>
      {todayCount > 0 && (
        <span className="sub-today-badge">{todayCount} oggi</span>
      )}
    </div>
  );
}

// ── Reddit tab ────────────────────────────────────────────────────────────────

function RedditTab({ redditAlerts, redditKws, loadingRD, subreddits, onAddSub, onRemoveSub, subPending }) {
  const highVel  = redditAlerts.filter(a => (a.velocity_pct ?? 0) >= 300);
  const maxCount = Math.max(...(redditKws ?? []).map(k => k.count), 1);

  // Sub names, stripping leading "r/" if present
  const subNames = subreddits.map(s => (s.value || s).replace(/^r\//i, ''));

  const subLabel = subNames.length
    ? subNames.slice(0, 2).map(n => `r/${n}`).join(', ') + (subNames.length > 2 ? '…' : '')
    : '—';

  return (
    <>
      <div className="kpi-grid-3">
        <KpiCard
          icon="👽"
          label="SUBREDDIT MONITORATI"
          value={subNames.length || '—'}
          sub={subLabel}
        />
        <KpiCard
          icon="📊"
          label="KEYWORD RILEVATE"
          value={(redditKws ?? []).length}
          sub="Con menzioni nelle ultime 72h"
        />
        <KpiCard
          icon="⚡"
          label="ALERT REDDIT"
          value={highVel.length}
          sub="Velocity ≥300%"
          tooltip={RD_ALERT_TOOLTIP}
        />
      </div>

      <div className="reddit-content-grid">
        {/* ── Left: keyword mentions ── */}
        <div className="card">
          <div className="trends-card-title">📊 KEYWORD MENZIONATE (72H)</div>
          {loadingRD ? (
            <p className="muted">Caricamento…</p>
          ) : (redditKws ?? []).length === 0 ? (
            <EmptyState icon="👽" message="Nessuna keyword trovata nelle ultime 72 ore." />
          ) : (
            <div>
              {(redditKws ?? []).slice(0, 10).map(kw => (
                <div key={kw.keyword} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ flex: 1, fontSize: 13 }}>{kw.keyword}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{kw.count} post</div>
                  <div style={{ width: 60, height: 4, background: 'var(--surface)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ width: `${Math.round((kw.count / maxCount) * 100)}%`, height: '100%', background: 'var(--accent)', borderRadius: 2 }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right column ── */}
        <div className="reddit-right-col">
          {/* Velocity alerts */}
          <div className="card">
            <div className="trends-card-title">
              ⚡ ALERT VELOCITY (72H)
              <InfoTooltip text={RD_VELOCITY_TOOLTIP} />
            </div>
            {redditAlerts.length === 0 ? (
              <EmptyState icon="⚡" message="Nessun alert velocity Reddit." />
            ) : (
              <div className="reddit-post-list">
                {redditAlerts.slice(0, 6).map(a => (
                  <RedditAlertCard key={a.id ?? a.keyword + a.sent_at} alert={a} />
                ))}
              </div>
            )}
          </div>

          {/* Subreddit list + manager */}
          <div className="card" style={{ marginTop: 14 }}>
            <div className="trends-card-title" style={{ marginBottom: 10 }}>👽 SUBREDDIT MONITORATI</div>
            <InlineListManager
              listKey="subreddits"
              items={subreddits}
              onAdd={onAddSub}
              onRemove={onRemoveSub}
              placeholder="r/subreddit_name"
              isPending={subPending}
              renderLabel={item => `r/${(item.value ?? item).replace(/^r\//i, '')}`}
              getUrl={item => `https://www.reddit.com/r/${(item.value ?? item).replace(/^r\//i, '')}`}
            />
          </div>
        </div>
      </div>
    </>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function NewsPage() {
  const [tab, setTab] = useState('news');
  const queryClient = useQueryClient();

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

  const { data: twitterAlerts = [], isLoading: loadingTA } = useQuery({
    queryKey: ['twitter-alerts', 48],
    queryFn: () => fetchTwitterAlerts(48),
    staleTime: 5 * 60_000,
  });

  // 48h — for the table
  const { data: twitterCounts48 = [], isLoading: loadingTC } = useQuery({
    queryKey: ['twitter-counts', 48],
    queryFn: () => fetchTwitterCounts(48),
    staleTime: 5 * 60_000,
  });

  // 7-day — for the KPI total tweet count
  const { data: twitterCounts7d = [] } = useQuery({
    queryKey: ['twitter-counts', 168],
    queryFn: () => fetchTwitterCounts(168),
    staleTime: 5 * 60_000,
  });

  // Reddit: filter dashboard alerts by source
  const { data: redditAlerts = [], isLoading: loadingRD } = useQuery({
    queryKey: ['reddit-alerts', 72],
    queryFn: () =>
      fetch('/api/dashboard/alerts?hours=72&limit=100')
        .then(r => r.json())
        .then(data =>
          data.filter(a =>
            (a.source ?? '').toLowerCase().includes('reddit') ||
            (a.alert_type ?? '').includes('reddit')
          )
        ),
    staleTime: 5 * 60_000,
  });

  // Reddit: keyword mentions from keyword_mentions table (source=reddit_apify)
  const { data: kwSources = {} } = useQuery({
    queryKey: ['keyword-sources', 72],
    queryFn: () => fetchKeywordSources(72),
    staleTime: 5 * 60_000,
  });
  const redditKws = Object.entries(kwSources)
    .map(([kw, sources]) => {
      const r = (sources ?? []).find(s => s.source === 'reddit_apify');
      return r ? { keyword: kw, count: r.count } : null;
    })
    .filter(Boolean)
    .sort((a, b) => b.count - a.count);

  // Config lists for subreddits
  const { data: configLists = {} } = useQuery({
    queryKey: ['config-lists'],
    queryFn: fetchConfigLists,
    staleTime: 30_000,
  });
  const subreddits = configLists.subreddits ?? [];

  const addSubMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });
  const removeSubMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const TABS = [
    { key: 'news',    label: `📰 News Detector (${newsCounts.length})` },
    { key: 'twitter', label: `🐦 Twitter/X (${twitterCounts48.length})` },
    { key: 'reddit',  label: `👽 Reddit (${redditKws.length})` },
  ];

  return (
    <>
      <Topbar title="📰 News, Twitter & Reddit" />
      <main className="page-content">

        {/* ── Tabs ── */}
        <div className="tabs">
          {TABS.map(t => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── News Detector ── */}
        {tab === 'news' && (
          <NewsTab
            newsAlerts={newsAlerts}
            newsCounts={newsCounts}
            loadingNA={loadingNA}
            loadingNC={loadingNC}
          />
        )}

        {/* ── Twitter/X ── */}
        {tab === 'twitter' && (
          <TwitterTab
            twitterCounts48={twitterCounts48}
            twitterCounts7d={twitterCounts7d}
            twitterAlerts={twitterAlerts}
            loadingTC={loadingTC}
            loadingTA={loadingTA}
          />
        )}

        {/* ── Reddit ── */}
        {tab === 'reddit' && (
          <RedditTab
            redditAlerts={redditAlerts}
            redditKws={redditKws}
            loadingRD={loadingRD}
            subreddits={subreddits}
            onAddSub={(lk, v) => addSubMutation.mutate({ listKey: lk, value: v })}
            onRemoveSub={(lk, v) => removeSubMutation.mutate({ listKey: lk, value: v })}
            subPending={addSubMutation.isPending || removeSubMutation.isPending}
          />
        )}

      </main>
    </>
  );
}
