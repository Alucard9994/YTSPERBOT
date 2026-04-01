import { useQuery } from '@tanstack/react-query';
import { useState, useMemo, useEffect } from 'react';
import {
  fetchAlerts, fetchKeywords, fetchConvergences,
  fetchBlacklist, fetchSchedule,
  fetchAlertsTimeline, fetchKeywordSources,
  fetchHighlights, fetchKeywordTimeseries,
  fetchKeywordSearch, fetchCompetitorVideos,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import { parseDate } from '../../utils/date.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  const d = parseDate(dateStr);
  if (!d) return '—';
  const min = Math.floor((Date.now() - d.getTime()) / 60_000);
  if (min < 1)  return 'adesso';
  if (min < 60) return `${min}m fa`;
  const h = Math.floor(min / 60);
  if (h < 24)   return `${h}h fa`;
  return `${Math.floor(h / 24)}g fa`;
}

function timeUntil(dateStr) {
  if (!dateStr) return '—';
  const d = parseDate(dateStr);
  if (!d) return '—';
  const diff = d.getTime() - Date.now();
  if (diff <= 0) return 'in attesa';
  const min = Math.floor(diff / 60_000);
  if (min < 60) return `tra ${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return `tra ${h}h${m > 0 ? ` ${m}m` : ''}`;
  return `tra ${Math.floor(h / 24)}g`;
}

const SRC_LABEL = {
  rss: 'RSS', rss_velocity: 'RSS', trending_rss: 'RSS',
  twitter: 'TW', twitter_apify: 'TW', twitter_trend: 'TW',
  youtube: 'YT', youtube_comments: 'YC',
  google_trends: 'GG', rising_query: 'GG',
  news: 'NEWS',
  pinterest: 'PT', pinterest_apify: 'PT',
  reddit: 'RD', reddit_apify: 'RD', reddit_apify_trend: 'RD',
  competitor_title: 'COMP', cross_signal: 'CROSS',
};
function srcLabel(s) { return SRC_LABEL[s] ?? s?.toUpperCase() ?? '?'; }

const SRC_COLOR = {
  rss: '#60a5fa', rss_velocity: '#60a5fa', trending_rss: '#60a5fa',
  news: '#22c55e',
  twitter: '#1d9bf0', twitter_apify: '#1d9bf0', twitter_trend: '#1d9bf0',
  google_trends: '#eab308', rising_query: '#eab308',
  reddit: '#ff4500', reddit_apify: '#ff4500', reddit_apify_trend: '#ff4500',
  youtube: '#e94560', youtube_comments: '#c084fc',
  pinterest: '#e60023', pinterest_apify: '#e60023',
  competitor_title: '#64748b',
  cross_signal: '#a855f7',
};
function srcColor(s) { return SRC_COLOR[s] ?? '#888'; }

function parseSources(a) {
  if (a.sources_list) return a.sources_list.split(',').filter(Boolean).map(s => s.trim());
  return a.source ? [a.source] : [];
}

function velClass(pct) {
  if (pct == null) return 'conv';
  if (pct >= 200) return 'high';
  if (pct >= 80)  return 'mid';
  return 'low';
}

function heatClass(kw, maxMentions) {
  const ratio = maxMentions > 0 ? (kw.total_mentions ?? 0) / maxMentions : 0;
  const n = kw.source_count ?? 1;
  if (ratio > 0.6 || n >= 4) return 'hot-1';
  if (ratio > 0.25 || n >= 3) return 'hot-2';
  if (ratio > 0.08 || n >= 2) return 'hot-3';
  return '';
}

function heatBarColor(hc) {
  if (hc === 'hot-1') return 'var(--accent)';
  if (hc === 'hot-2') return 'var(--yellow)';
  if (hc === 'hot-3') return 'var(--green)';
  return 'var(--border)';
}

// ── StatusPill ────────────────────────────────────────────────────────────────

function StatusPill({ icon, label, value, variant }) {
  return (
    <div className={`status-pill${variant ? ` ${variant}` : ''}`}>
      <div className="status-pill-icon">{icon}</div>
      <div>
        <div className="status-pill-value">{value}</div>
        <div className="status-pill-label">{label}</div>
      </div>
    </div>
  );
}

// ── PulseCard ─────────────────────────────────────────────────────────────────

function PulseCard({ alerts, convergences }) {
  const best = useMemo(() => {
    const byVel = [...alerts].sort((a, b) => (b.velocity_pct ?? 0) - (a.velocity_pct ?? 0));
    if (byVel.length > 0) return byVel[0];
    if (convergences.length > 0) {
      const c = convergences[0];
      return {
        keyword: c.keyword, velocity_pct: null,
        sources_list: c.sources, sent_at: c.last_seen,
        is_conv: true, total_mentions: c.total_mentions,
      };
    }
    return null;
  }, [alerts, convergences]);

  if (!best) {
    return (
      <div className="pulse-card">
        <div className="pulse-label">
          <span className="pulse-label-dot" />
          Segnale più forte — ultime 48h
        </div>
        <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '8px 0' }}>
          Nessun segnale registrato. Il bot è in ascolto.
        </div>
      </div>
    );
  }

  const sources = parseSources(best);

  return (
    <div className="pulse-card">
      <div className="pulse-label">
        <span className="pulse-label-dot" />
        Segnale più forte — ultime 48h
      </div>
      <div className="pulse-keyword">{best.keyword}</div>
      <div className="pulse-stats">
        {best.total_mentions != null && (
          <span className="pulse-stat">
            <strong>{best.total_mentions.toLocaleString('it-IT')}</strong> menzioni
          </span>
        )}
        {best.velocity_pct != null && (
          <span className="pulse-stat">
            <strong style={{ color: 'var(--accent)' }}>+{Math.round(best.velocity_pct)}%</strong> velocity
          </span>
        )}
        {sources.length > 0 && (
          <span className="pulse-stat">
            <strong>{sources.length}</strong> {sources.length === 1 ? 'fonte' : 'fonti'}
          </span>
        )}
        <span className="pulse-stat">{timeAgo(best.sent_at)}</span>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {sources.map(s => (
          <span
            key={s}
            className="platform-pill"
            style={{ color: srcColor(s), borderColor: `${srcColor(s)}44` }}
          >
            {srcLabel(s)}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── SignalFeed ────────────────────────────────────────────────────────────────

const FEED_FILTERS = [
  { key: 'all',          label: 'Tutti' },
  { key: 'velocity',     label: '🔥 Velocity' },
  { key: 'cross_signal', label: '🔗 Convergenza' },
  { key: 'rss',          label: '📡 RSS' },
  { key: 'reddit',       label: '🤖 Reddit' },
  { key: 'twitter',      label: '🐦 Twitter' },
];

function matchesFilter(item, filter) {
  if (filter === 'all') return true;
  if (filter === 'cross_signal') return item.is_conv || item.type === 'cross_signal';
  if (filter === 'velocity')
    return !item.is_conv && item.velocity_pct != null &&
      !['rss_velocity','trending_rss','reddit_apify_trend','twitter_trend','pinterest_apify','news'].includes(item.type);
  if (filter === 'rss')     return ['rss_velocity', 'trending_rss'].includes(item.type);
  if (filter === 'reddit')  return item.type === 'reddit_apify_trend';
  if (filter === 'twitter') return item.type === 'twitter_trend';
  return true;
}

function typeToColor(type, is_conv) {
  if (is_conv) return SRC_COLOR.cross_signal;
  return SRC_COLOR[type] ?? 'var(--text-muted)';
}

function SignalFeed({ alerts, convergences }) {
  const [filter, setFilter] = useState('all');

  const feedItems = useMemo(() => {
    const alertItems = alerts.map(a => ({
      id:             `a-${a.id ?? a.keyword}`,
      type:           a.alert_type || 'velocity',
      keyword:        a.keyword,
      velocity_pct:   a.velocity_pct,
      sources:        parseSources(a),
      time:           a.sent_at,
      total_mentions: a.total_mentions ?? null,
      is_conv:        false,
    }));

    const convItems = convergences.map(c => ({
      id:             `c-${c.keyword}`,
      type:           'cross_signal',
      keyword:        c.keyword,
      velocity_pct:   null,
      sources:        (c.sources ?? '').split(',').filter(Boolean),
      time:           c.last_seen,
      total_mentions: c.total_mentions,
      source_count:   c.source_count,
      is_conv:        true,
    }));

    // Merge, dedup by keyword (alerts take priority)
    const seen   = new Set();
    const merged = [];
    for (const item of [...alertItems, ...convItems]) {
      if (!seen.has(item.keyword)) {
        seen.add(item.keyword);
        merged.push(item);
      }
    }
    return merged.sort((a, b) => {
      const ta = parseDate(a.time)?.getTime() ?? 0;
      const tb = parseDate(b.time)?.getTime() ?? 0;
      return tb - ta;
    });
  }, [alerts, convergences]);

  const filtered = feedItems.filter(item => matchesFilter(item, filter));

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 700 }}>🔥 Feed segnali recenti</span>
        <span className="muted" style={{ fontSize: 11 }}>
          {feedItems.length} segnali totali
        </span>
      </div>

      <div className="feed-filter-row">
        {FEED_FILTERS.map(f => (
          <button
            key={f.key}
            className={`feed-filter-btn${filter === f.key ? ' active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
          Nessun segnale per il filtro selezionato.
        </div>
      ) : (
        <div className="feed-list">
          {filtered.slice(0, 15).map(item => (
            <div key={item.id} className="feed-item">
              <div className="feed-dot" style={{ background: typeToColor(item.type, item.is_conv) }} />
              <div className="feed-body">
                <div className="feed-keyword">{item.keyword}</div>
                <div className="feed-meta">
                  {item.sources.slice(0, 4).map(s => (
                    <span key={s} style={{ color: srcColor(s), fontWeight: 600 }}>{srcLabel(s)}</span>
                  ))}
                  {item.total_mentions != null && (
                    <span>{item.total_mentions.toLocaleString('it-IT')} menzioni</span>
                  )}
                  {item.source_count != null && !item.total_mentions && (
                    <span>{item.source_count} fonti</span>
                  )}
                </div>
              </div>
              <div className="feed-right">
                {item.velocity_pct != null ? (
                  <span className={`vel-badge ${velClass(item.velocity_pct)}`}>
                    +{Math.round(item.velocity_pct)}%
                  </span>
                ) : item.is_conv ? (
                  <span className="vel-badge conv">
                    🔗 {item.source_count ?? item.sources.length} fonti
                  </span>
                ) : null}
                <span className="feed-time">{timeAgo(item.time)}</span>
              </div>
            </div>
          ))}
          {filtered.length > 15 && (
            <div style={{ textAlign: 'center', padding: '8px 0', fontSize: 12, color: 'var(--text-dim)' }}>
              + {filtered.length - 15} altri segnali
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── KeywordHeatmap ────────────────────────────────────────────────────────────

const KW_PERIODS = [
  { h: 24,  label: '24h' },
  { h: 168, label: '7 giorni' },
  { h: 720, label: '30 giorni' },
];

function KeywordHeatmap({ keywords, sourcesMap, onSelectKw, hours, onHoursChange }) {
  const topKws = useMemo(
    () => [...keywords].sort((a, b) => (b.total_mentions ?? 0) - (a.total_mentions ?? 0)).slice(0, 20),
    [keywords],
  );
  const maxMentions = useMemo(
    () => Math.max(...topKws.map(k => k.total_mentions ?? 0), 1),
    [topKws],
  );

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span className="section-heading" style={{ margin: 0 }}>🌡️ Keyword Heatmap</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {KW_PERIODS.map(p => (
            <button
              key={p.h}
              className={`kw-period-btn${hours === p.h ? ' active' : ''}`}
              onClick={() => onHoursChange(p.h)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {topKws.length === 0 ? (
        <div className="card">
          <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            Nessuna keyword nel periodo selezionato.
          </div>
        </div>
      ) : (
        <div className="kw-heatmap-grid">
          {topKws.map(kw => {
            const hc     = heatClass(kw, maxMentions);
            const barW   = `${Math.max(5, ((kw.total_mentions ?? 0) / maxMentions) * 100)}%`;
            const srcs   = (kw.sources ?? '').split(',').filter(Boolean);
            const detail = sourcesMap[kw.keyword];

            return (
              <div
                key={kw.keyword}
                className={`kw-heatmap-card${hc ? ` ${hc}` : ''}`}
                onClick={() => onSelectKw(kw.keyword)}
                title={`Clicca per esplorare "${kw.keyword}"`}
              >
                <div className="kw-heat-name">{kw.keyword}</div>
                <div className="kw-heat-value">{(kw.total_mentions ?? 0).toLocaleString('it-IT')}</div>
                <div className="kw-heat-sub">
                  {kw.source_count ?? 1} {(kw.source_count ?? 1) === 1 ? 'fonte' : 'fonti'}
                  {' · '}{timeAgo(kw.last_seen)}
                </div>
                <div className="kw-heat-pills">
                  {srcs.slice(0, 3).map(s => (
                    <span key={s} className="kw-heat-pill" style={{ color: srcColor(s) }}>
                      {srcLabel(s)}
                    </span>
                  ))}
                </div>
                {detail && detail.length > 0 && (
                  <div style={{ marginTop: 6, display: 'flex', height: 2, borderRadius: 1, overflow: 'hidden', gap: 1 }}>
                    {detail.map(({ source, count }) => (
                      <div
                        key={source}
                        title={`${srcLabel(source)}: ${count}`}
                        style={{
                          width: `${(count / (kw.total_mentions || 1)) * 100}%`,
                          background: srcColor(source),
                          minWidth: 2,
                        }}
                      />
                    ))}
                  </div>
                )}
                <div className="kw-heat-bar">
                  <div className="kw-heat-bar-fill" style={{ width: barW, background: heatBarColor(hc) }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── ContentOutperformer ───────────────────────────────────────────────────────

const OUTPERF_TABS = [
  { key: 'youtube',    label: '▶️ YouTube' },
  { key: 'tiktok',     label: '🎵 TikTok' },
  { key: 'instagram',  label: '📸 Instagram' },
  { key: 'competitor', label: '🏆 Competitor' },
];

function ContentItem({ item, platform }) {
  const emoji  = { youtube: '▶️', tiktok: '🎵', instagram: '📸', competitor: '🏆' }[platform] ?? '🎬';
  const isLink = platform === 'youtube' || platform === 'competitor';
  const title  = item.video_title ?? item.title ?? item.caption?.slice(0, 60) ?? '—';
  const multi  = item.multiplier_avg ?? item.multiplier ?? null;
  const href   = isLink
    ? (item.video_url ?? `https://youtube.com/watch?v=${item.video_id}`)
    : (item.video_url ?? item.url);
  const author = item.channel_name ?? item.display_name ?? item.username;
  const views  = item.views ?? 0;

  return (
    <div className="content-item">
      <div className="content-thumb">{emoji}</div>
      <div className="content-body">
        <div className="content-title">
          {href
            ? <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>{title}</a>
            : title}
        </div>
        <div className="content-meta">
          <span>👁 {views.toLocaleString('it-IT')}</span>
          {author && <span>· {author}</span>}
          {item.keyword && <span>· {item.keyword}</span>}
        </div>
      </div>
      {multi != null && (
        <div className="content-right">
          <span className="content-multiplier">{Number(multi).toFixed(1)}×</span>
          <span className="content-views">vs media</span>
        </div>
      )}
    </div>
  );
}

function ContentOutperformer({ highlights, competitorVideos }) {
  const [activeTab, setActiveTab] = useState('youtube');

  const itemsByTab = {
    youtube:    highlights?.youtube_top ?? [],
    tiktok:     (highlights?.social_top ?? []).filter(v => v.platform === 'tiktok'),
    instagram:  (highlights?.social_top ?? []).filter(v => v.platform === 'instagram'),
    competitor: (competitorVideos ?? []).slice(0, 5),
  };

  const items = itemsByTab[activeTab] ?? [];

  return (
    <div style={{ marginBottom: 20 }}>
      <div className="section-heading" style={{ marginBottom: 10 }}>
        🎬 Contenuti Outperformer
      </div>
      <div className="card">
        <div className="outperf-tabs">
          {OUTPERF_TABS.map(t => (
            <button
              key={t.key}
              className={`outperf-tab${activeTab === t.key ? ' active' : ''}`}
              onClick={() => setActiveTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {items.length === 0 ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '16px 0', textAlign: 'center' }}>
            Nessun dato disponibile per questa piattaforma.
          </div>
        ) : (
          items.map((item, i) => (
            <ContentItem
              key={item.video_id ?? item.id ?? i}
              item={item}
              platform={activeTab}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ── AlertTimelineSidebar ──────────────────────────────────────────────────────

function AlertTimelineSidebar({ data }) {
  if (!data || data.length === 0) return (
    <div className="card" style={{ padding: '12px 14px' }}>
      <div style={{ color: 'var(--text-dim)', fontSize: 11, textAlign: 'center', padding: '8px 0' }}>
        Nessun dato timeline.
      </div>
    </div>
  );

  const recent = data.slice(-14);
  const max    = Math.max(...recent.map(d => d.count), 1);
  const BAR_MAX = 40;

  return (
    <div className="card" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: BAR_MAX + 16 }}>
        {recent.map(({ day, count }) => {
          const h = Math.max(3, Math.round((count / max) * BAR_MAX));
          return (
            <div
              key={day}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}
              title={`${day}: ${count} alert`}
            >
              <div style={{
                width: '100%', height: h,
                background: count > 0 ? 'var(--accent)' : 'var(--border)',
                borderRadius: '2px 2px 0 0',
                opacity: count > 0 ? 0.85 : 0.3,
                transition: 'height .3s',
              }} />
              <span style={{
                fontSize: 7, color: 'var(--text-dim)',
                writingMode: 'vertical-rl', transform: 'rotate(180deg)', lineHeight: 1,
              }}>
                {day.slice(5)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── PlatformSignals ───────────────────────────────────────────────────────────

function PlatformSignals({ highlights }) {
  const platforms = [
    { key: 'reddit',    icon: '🤖', label: 'Reddit',      item: highlights?.reddit_top },
    { key: 'twitter',   icon: '🐦', label: 'Twitter / X', item: highlights?.twitter_top },
    { key: 'pinterest', icon: '📌', label: 'Pinterest',   item: highlights?.pinterest_top },
    { key: 'news',      icon: '📰', label: 'News',        item: highlights?.news_top },
  ];

  return (
    <div>
      {platforms.map(({ key, icon, label, item }) => (
        <div key={key} className="plat-signal">
          <div className="plat-icon">{icon}</div>
          <div className="plat-body">
            <div className="plat-name">{label}</div>
            {item
              ? <div className="plat-kw">{item.keyword}</div>
              : <div className="plat-empty">Nessun segnale recente</div>
            }
          </div>
          {item?.velocity_pct != null ? (
            <div className="plat-vel">+{Math.round(item.velocity_pct)}%</div>
          ) : item ? (
            <div style={{ fontSize: 10, color: 'var(--text-dim)', flexShrink: 0 }}>
              {timeAgo(item.sent_at)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

// ── KeywordExplorerSidebar ────────────────────────────────────────────────────

function KeywordExplorerSidebar({ externalKw }) {
  const [inputKw, setInputKw] = useState('');
  const [hours,   setHours]   = useState(168);

  // Sync from heatmap click
  useEffect(() => {
    if (externalKw) setInputKw(externalKw);
  }, [externalKw]);

  const kwToFetch = inputKw.trim();

  const { data: breakdown, isFetching: bdFetching } = useQuery({
    queryKey:  ['kw-search', kwToFetch, hours],
    queryFn:   () => fetchKeywordSearch(kwToFetch, hours),
    enabled:   kwToFetch.length > 0,
    staleTime: 5 * 60_000,
  });

  const { data: series = [], isFetching: seriesFetching } = useQuery({
    queryKey:  ['kw-timeseries', kwToFetch, hours],
    queryFn:   () => fetchKeywordTimeseries(kwToFetch, hours),
    enabled:   kwToFetch.length > 0,
    staleTime: 5 * 60_000,
  });

  const isFetching    = bdFetching || seriesFetching;
  const totalMentions = breakdown?.total ?? 0;
  const maxSeries     = Math.max(...series.map(p => p.total), 1);

  return (
    <div className="card" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'center' }}>
        <input
          className="explorer-sb-input"
          style={{ margin: 0, flex: 1 }}
          type="text"
          placeholder="Cerca keyword…"
          value={inputKw}
          onChange={e => setInputKw(e.target.value)}
        />
        <select
          value={hours}
          onChange={e => setHours(Number(e.target.value))}
          style={{
            background: 'var(--surface2)', color: 'var(--text)',
            border: '1px solid var(--border)', borderRadius: 6,
            padding: '6px 8px', fontSize: 11, flexShrink: 0,
          }}
        >
          <option value={24}>24h</option>
          <option value={168}>7g</option>
          <option value={720}>30g</option>
        </select>
      </div>

      {!kwToFetch ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 11, textAlign: 'center', padding: '10px 0' }}>
          Clicca una keyword dalla heatmap o digita qui
        </div>
      ) : isFetching ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>⏳ Caricamento…</div>
      ) : totalMentions === 0 ? (
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          Nessuna menzione per <b>{kwToFetch}</b>.
        </div>
      ) : (
        <div className="explorer-sb-result">
          <div className="explorer-sb-total">
            {totalMentions.toLocaleString('it-IT')}
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 5 }}>
              menzioni · {breakdown.source_count} {breakdown.source_count === 1 ? 'fonte' : 'fonti'}
            </span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
            <strong style={{ color: 'var(--accent)' }}>{kwToFetch}</strong>
            {' · '}ultimi{' '}
            {hours >= 720 ? '30 giorni' : hours >= 168 ? '7 giorni' : '24h'}
          </div>

          {/* Source bars */}
          <div className="explorer-sb-sources">
            {(breakdown.sources ?? []).map(({ source, count }) => (
              <div key={source} className="explorer-sb-src-row">
                <span style={{ width: 28, color: srcColor(source), fontWeight: 700, fontSize: 10 }}>
                  {srcLabel(source)}
                </span>
                <div className="explorer-sb-bar-bg">
                  <div
                    className="explorer-sb-bar-fill"
                    style={{ width: `${(count / totalMentions) * 100}%`, background: srcColor(source) }}
                  />
                </div>
                <span className="explorer-sb-count">{count}</span>
              </div>
            ))}
          </div>

          {/* Mini sparkline */}
          {series.length > 0 && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'flex-end', gap: 2, height: 32 }}>
              {series.map(({ hour_bucket, total }) => (
                <div
                  key={hour_bucket}
                  title={`${hour_bucket}: ${total}`}
                  style={{ flex: '1 0 0', minWidth: 3, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
                >
                  <div style={{
                    width: '100%',
                    height: Math.max(2, Math.round((total / maxSeries) * 28)),
                    background: 'var(--accent)',
                    borderRadius: '2px 2px 0 0',
                    opacity: 0.75,
                  }} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── ScheduleMini ──────────────────────────────────────────────────────────────

function ScheduleMini({ schedule }) {
  const shown = schedule.slice(0, 6);

  if (shown.length === 0) {
    return (
      <div className="card" style={{ padding: '12px 14px' }}>
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>Nessun dato scheduler.</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: '10px 12px' }}>
      {shown.map(job => (
        <div key={job.name} className="sched-mini-row">
          <div className="sched-mini-dot" style={{ background: job.active ? 'var(--green)' : 'var(--text-dim)' }} />
          <span className="sched-mini-name">{job.name}</span>
          <span className="sched-mini-next">
            {job.next_run
              ? timeUntil(job.next_run)
              : job.last_run
                ? timeAgo(job.last_run)
                : '—'}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [kwHours,    setKwHours]    = useState(168);
  const [explorerKw, setExplorerKw] = useState('');

  const { data: alerts24 = [] } = useQuery({
    queryKey: ['alerts', 24],
    queryFn:  () => fetchAlerts(24, 50),
    staleTime: 2 * 60_000,
  });

  const { data: alerts168 = [] } = useQuery({
    queryKey: ['alerts', 168],
    queryFn:  () => fetchAlerts(168, 200),
    staleTime: 5 * 60_000,
  });

  const { data: keywords = [] } = useQuery({
    queryKey: ['keywords', kwHours],
    queryFn:  () => fetchKeywords(kwHours, 20),
    staleTime: 5 * 60_000,
  });

  const { data: convergences = [] } = useQuery({
    queryKey: ['convergences', 48],
    queryFn:  () => fetchConvergences(48, 2),
    staleTime: 2 * 60_000,
  });

  const { data: schedule = [] } = useQuery({
    queryKey: ['schedule'],
    queryFn:  fetchSchedule,
    staleTime: 30 * 60_000,
  });

  const { data: alertsTimeline = [] } = useQuery({
    queryKey: ['alerts-timeline'],
    queryFn:  () => fetchAlertsTimeline(14),
    staleTime: 10 * 60_000,
  });

  const { data: keywordSourcesMap = {} } = useQuery({
    queryKey: ['keyword-sources', kwHours],
    queryFn:  () => fetchKeywordSources(kwHours, 20),
    staleTime: 10 * 60_000,
  });

  const { data: highlights } = useQuery({
    queryKey: ['highlights'],
    queryFn:  fetchHighlights,
    staleTime: 5 * 60_000,
  });

  const { data: competitorVideos = [] } = useQuery({
    queryKey: ['competitor-videos', 168],
    queryFn:  () => fetchCompetitorVideos(168, 20),
    staleTime: 10 * 60_000,
  });

  // Derived
  const activeModules = schedule.filter(j => j.active).length;
  const totalModules  = schedule.length;

  // Suppress unused warning (alerts24 used for today count)
  void alerts24;

  return (
    <>
      <Topbar title="🏠 Dashboard" />
      <main className="page-content">
        <div className="dash-grid">

          {/* ══ MAIN ══════════════════════════════════════════════════════ */}
          <div className="dash-main">

            {/* Status pills */}
            <div className="status-pills">
              <StatusPill icon="🔔" label="Alert oggi"         value={alerts24.length}   variant="pill-alert" />
              <StatusPill icon="🔗" label="Convergenze 48h"    value={convergences.length} />
              <StatusPill icon="⚙️" label="Moduli attivi"      value={totalModules ? `${activeModules}/${totalModules}` : '—'} variant="pill-active" />
              <StatusPill icon="🏷️" label="Keyword monitorate" value={keywords.length} />
            </div>

            {/* Pulse — top signal */}
            <PulseCard alerts={alerts168} convergences={convergences} />

            {/* Unified signal feed */}
            <SignalFeed alerts={alerts168} convergences={convergences} />

            {/* Keyword heatmap */}
            <KeywordHeatmap
              keywords={keywords}
              sourcesMap={keywordSourcesMap}
              onSelectKw={kw => setExplorerKw(kw)}
              hours={kwHours}
              onHoursChange={setKwHours}
            />

            {/* Content outperformer */}
            <ContentOutperformer
              highlights={highlights}
              competitorVideos={competitorVideos}
            />

          </div>

          {/* ══ SIDEBAR ═══════════════════════════════════════════════════ */}
          <div className="dash-sidebar">

            <div className="sidebar-section">
              <div className="sidebar-section-title">Segnali piattaforma</div>
              <PlatformSignals highlights={highlights} />
            </div>

            <div className="sidebar-section">
              <div className="sidebar-section-title">Volume alert — 14 giorni</div>
              <AlertTimelineSidebar data={alertsTimeline} />
            </div>

            <div className="sidebar-section">
              <div className="sidebar-section-title">Esplora keyword</div>
              <KeywordExplorerSidebar externalKw={explorerKw} />
            </div>

            <div className="sidebar-section">
              <div className="sidebar-section-title">Prossime esecuzioni</div>
              <ScheduleMini schedule={schedule} />
            </div>

          </div>
        </div>
      </main>
    </>
  );
}
