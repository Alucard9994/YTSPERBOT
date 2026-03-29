import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  fetchAlerts, fetchKeywords, fetchConvergences,
  fetchBlacklist, fetchSchedule,
  fetchAlertsTimeline, fetchKeywordSources,
  fetchHighlights, fetchKeywordTimeseries,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import { parseDate } from '../../utils/date.js';

// ── helpers ───────────────────────────────────────────────────────────────────

const AVATAR_COLORS = [
  '#7c3aed', '#dc2626', '#d97706', '#059669',
  '#2563eb', '#db2777', '#0891b2', '#65a30d',
];
function avatarColor(str = '') {
  let h = 0;
  for (const c of str) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
function avatarInitials(str = '') {
  const w = str.trim().split(/\s+/);
  return w.length >= 2
    ? (w[0][0] + w[1][0]).toUpperCase()
    : str.slice(0, 2).toUpperCase();
}

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

const SRC_LABEL = {
  rss: 'RSS', twitter: 'TW', twitter_apify: 'TW',
  youtube: 'YT', youtube_comments: 'YC',
  google_trends: 'GG', news: 'NEWS',
  pinterest: 'PT', reddit: 'RD',
  competitor_title: 'COMP', cross_signal: 'CROSS',
};
function srcLabel(s) { return SRC_LABEL[s] ?? s?.toUpperCase() ?? '?'; }

function parseSources(a) {
  if (a.sources_list) return a.sources_list.split(',').filter(Boolean).map(s => s.trim());
  return a.source ? [a.source] : [];
}

function priorityBarColor(p) {
  if ((p ?? 5) >= 8) return 'var(--danger)';
  if ((p ?? 5) >= 6) return 'var(--yellow)';
  return 'var(--green)';
}

function fontiBadgeColor(n) {
  if (n >= 5) return '#dc2626';
  if (n >= 4) return '#ea580c';
  if (n >= 3) return '#ca8a04';
  return '#16a34a';
}


const CONV_TOOLTIP =
  'Convergenza = la stessa keyword appare su 2+ piattaforme diverse nelle ultime 48 ore. Segnale affidabile di trend emergente.';
const KW_TOOLTIP =
  'Top keyword per numero totale di menzioni nelle ultime 7 giorni, su tutte le fonti monitorate.';
const ALERT_TOOLTIP =
  'Alert Telegram inviati nelle ultime 24 ore (o 7 giorni come fallback), ordinati per priorità. La barra indica l\'intensità del segnale. Se vuoto: nessuna soglia di velocity è stata superata recentemente — vedi la sezione Convergenze per i segnali attivi.';

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

function AlertItem({ alert: a }) {
  const sources = parseSources(a);
  const prio     = a.priority ?? 5;
  const color    = avatarColor(a.keyword);
  const barW     = `${Math.min(100, (prio / 10) * 100)}%`;
  const barColor = priorityBarColor(prio);

  return (
    <div className="alert-item">
      <div
        className="alert-avatar"
        style={{ background: `${color}22`, border: `1.5px solid ${color}55` }}
      >
        <span style={{ color, fontWeight: 700 }}>{avatarInitials(a.keyword)}</span>
      </div>
      <div className="alert-body">
        <div className="alert-top">
          <div className="alert-top-left">
            <span className="alert-keyword">{a.keyword}</span>
            {a.velocity_pct != null && (
              <span className="alert-velocity">+{Math.round(a.velocity_pct)}%</span>
            )}
          </div>
          <div className="alert-sources">
            {sources.map(s => (
              <span key={s} className="alert-source-badge">{srcLabel(s)}</span>
            ))}
          </div>
        </div>
        <div className="alert-progress-wrap">
          <div className="alert-progress-bar" style={{ width: barW, background: barColor }} />
        </div>
        <div className="alert-meta">Priorità {prio}/10 · {timeAgo(a.sent_at)}</div>
      </div>
    </div>
  );
}

function KeywordRow({ rank, kw, sourcesDetail }) {
  const n      = kw.source_count ?? 1;
  const color  = fontiBadgeColor(n);
  const fires  = n >= 4 ? '🔥🔥' : '🔥';
  const srcs   = (kw.sources ?? '').split(',').filter(Boolean);

  return (
    <tr className="kw-rank-row">
      <td><span className="kw-rank-num">{rank}</span></td>
      <td>
        <span className="kw-rank-name">{kw.keyword}</span>
        {sourcesDetail && <SourceBar sourcesDetail={sourcesDetail} />}
      </td>
      <td><span className="kw-rank-mentions">{(kw.total_mentions ?? 0).toLocaleString('it-IT')}</span></td>
      <td>
        <div
          className="fonti-badge"
          style={{ background: `${color}22`, border: `1.5px solid ${color}44` }}
        >
          <span style={{ color, fontWeight: 800, fontSize: 13, lineHeight: 1 }}>{n}</span>
          <span style={{ color, fontSize: 9, opacity: 0.85 }}>fonti</span>
          <span style={{ fontSize: 9 }}>{fires}</span>
        </div>
      </td>
      <td>
        <div className="platform-pills">
          {srcs.map(s => (
            <span key={s} className="platform-pill">{srcLabel(s)}</span>
          ))}
        </div>
      </td>
      <td><span className="muted" style={{ fontSize: 12 }}>{timeAgo(kw.last_seen)}</span></td>
    </tr>
  );
}

function ConvergenceItem({ item }) {
  const srcs  = (item.sources ?? '').split(',').filter(Boolean);
  const n     = item.source_count ?? srcs.length;
  const color = fontiBadgeColor(n);
  return (
    <div className="alert-item">
      <div
        className="alert-avatar"
        style={{ background: `${color}22`, border: `1.5px solid ${color}55` }}
      >
        <span style={{ color, fontWeight: 700 }}>🔗</span>
      </div>
      <div className="alert-body">
        <div className="alert-top">
          <div className="alert-top-left">
            <span className="alert-keyword">{item.keyword}</span>
            <span className="alert-velocity">{n} fonti</span>
          </div>
          <div className="alert-sources">
            {srcs.map(s => (
              <span key={s} className="alert-source-badge">{srcLabel(s)}</span>
            ))}
          </div>
        </div>
        <div className="alert-progress-wrap">
          <div
            className="alert-progress-bar"
            style={{
              width: `${Math.min(100, (n / 5) * 100)}%`,
              background: color,
            }}
          />
        </div>
        <div className="alert-meta">
          {item.total_mentions} menzioni · {timeAgo(item.last_seen)}
        </div>
      </div>
    </div>
  );
}

// ── Alert Timeline ────────────────────────────────────────────────────────────

const SRC_COLOR = {
  rss: '#4f8ef7', news: '#22c55e', twitter: '#1d9bf0', twitter_apify: '#1d9bf0',
  google_trends: '#f59e0b', reddit: '#ff4500', youtube: '#e94560',
  youtube_comments: '#c084fc', pinterest: '#e60023', competitor_title: '#64748b',
};
function srcColor(s) { return SRC_COLOR[s] ?? '#888'; }

function AlertTimeline({ data }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.count), 1);
  const BAR_MAX_H = 40;
  return (
    <div style={{ marginTop: 14 }}>
      <div className="section-heading" style={{ marginBottom: 8 }}>
        📅 Volume alert — ultimi 14 giorni
      </div>
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: BAR_MAX_H + 20 }}>
          {data.map(({ day, count }) => {
            const barH = Math.max(3, Math.round((count / max) * BAR_MAX_H));
            const label = day.slice(5); // MM-DD
            return (
              <div
                key={day}
                style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}
                title={`${day}: ${count} alert`}
              >
                <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>{count > 0 ? count : ''}</span>
                <div
                  style={{
                    width: '100%', height: barH,
                    background: count > 0 ? 'var(--accent)' : 'var(--surface-alt, #222)',
                    borderRadius: '3px 3px 0 0',
                    transition: 'height .3s',
                    opacity: count > 0 ? 1 : 0.3,
                  }}
                />
                <span style={{ fontSize: 8, color: 'var(--text-dim)', writingMode: 'vertical-rl', transform: 'rotate(180deg)', lineHeight: 1 }}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SourceBar({ sourcesDetail }) {
  if (!sourcesDetail || sourcesDetail.length === 0) return null;
  const total = sourcesDetail.reduce((s, r) => s + r.count, 0);
  return (
    <div style={{ marginTop: 4 }}>
      {/* Barra segmentata */}
      <div style={{ display: 'flex', height: 4, borderRadius: 2, overflow: 'hidden', gap: 1 }}>
        {sourcesDetail.map(({ source, count }) => (
          <div
            key={source}
            title={`${srcLabel(source)}: ${count}`}
            style={{
              width: `${(count / total) * 100}%`,
              background: srcColor(source),
              minWidth: 2,
            }}
          />
        ))}
      </div>
      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 8px', marginTop: 3 }}>
        {sourcesDetail.map(({ source, count }) => (
          <span key={source} style={{ fontSize: 9, color: 'var(--text-dim)' }}>
            <span style={{ color: srcColor(source), fontWeight: 700 }}>●</span> {srcLabel(source)} {count}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Highlights components ─────────────────────────────────────────────────────

const PLATFORM_EMOJI = { tiktok: '🎵', instagram: '📸', youtube: '▶️' };
const SIGNAL_EMOJI   = { reddit: '🤖', twitter: '🐦', pinterest: '📌', news: '📰' };

function HighlightVideoCard({ item, platform }) {
  const emoji = PLATFORM_EMOJI[platform] ?? PLATFORM_EMOJI[item?.platform] ?? '🎬';
  const isYT  = platform === 'youtube' || item?.video_id && !item?.platform;
  const title = item?.title || '—';
  const multi = item?.multiplier_avg ?? item?.multiplier;
  const href  = isYT
    ? `https://youtube.com/watch?v=${item?.video_id}`
    : item?.url;

  return (
    <div className="highlight-card">
      <div className="highlight-card-header">
        <span className="highlight-platform-badge">{emoji} {(platform || item?.platform || 'video').toUpperCase()}</span>
        {multi != null && (
          <span className="highlight-multiplier">{multi.toFixed(1)}×</span>
        )}
      </div>
      <div className="highlight-title">
        {href
          ? <a href={href} target="_blank" rel="noopener noreferrer">{title}</a>
          : title}
      </div>
      <div className="highlight-meta">
        <span>👁 {(item?.views ?? 0).toLocaleString()}</span>
        {item?.channel_name && <span> · {item.channel_name}</span>}
        {item?.username && <span> · @{item.username}</span>}
      </div>
    </div>
  );
}

function HighlightCommentCard({ item }) {
  if (!item) return null;
  return (
    <div className="highlight-card">
      <div className="highlight-card-header">
        <span className="highlight-platform-badge">💬 COMMENTO</span>
        {item.likes > 0 && <span className="highlight-multiplier">👍 {item.likes}</span>}
      </div>
      <div className="highlight-title" style={{ fontStyle: 'italic', fontSize: 13 }}>
        "{item.comment_text?.slice(0, 120)}{item.comment_text?.length > 120 ? '…' : ''}"
      </div>
      <div className="highlight-meta">
        {item.video_title && <span>📹 {item.video_title.slice(0, 50)}</span>}
        {item.category && <span> · {item.category}</span>}
      </div>
    </div>
  );
}

function HighlightSignalCard({ label, item, source }) {
  if (!item) {
    return (
      <div className="highlight-card highlight-card--empty">
        <span className="highlight-platform-badge">{SIGNAL_EMOJI[source] ?? '📡'} {label}</span>
        <div className="highlight-empty-msg">Nessun segnale recente</div>
      </div>
    );
  }
  return (
    <div className="highlight-card">
      <div className="highlight-card-header">
        <span className="highlight-platform-badge">{SIGNAL_EMOJI[source] ?? '📡'} {label}</span>
        {item.velocity_pct != null && (
          <span className="highlight-multiplier">+{Math.round(item.velocity_pct)}%</span>
        )}
      </div>
      <div className="highlight-title">{item.keyword}</div>
      <div className="highlight-meta">{timeAgo(item.sent_at)}</div>
    </div>
  );
}

function HighlightsSection({ data }) {
  if (!data) return null;
  const { youtube_top = [], social_top = [], comments_top = [],
          reddit_top, twitter_top, pinterest_top, news_top } = data;

  const hasContent = youtube_top.length + social_top.length + comments_top.length > 0;

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="section-heading" style={{ marginBottom: 10 }}>
        🎯 Highlights del momento
        <InfoTooltip text="I migliori contenuti e segnali aggregati da tutte le fonti." />
      </div>

      {/* Row 1: video YT + social + commenti */}
      {hasContent && (
        <div className="highlights-grid-3" style={{ marginBottom: 12 }}>
          {/* YouTube top 3 */}
          <div>
            <div className="highlight-group-label">▶️ YouTube outperformer</div>
            {youtube_top.length === 0
              ? <div className="highlight-card highlight-card--empty"><div className="highlight-empty-msg">Nessun dato</div></div>
              : youtube_top.map(v => <HighlightVideoCard key={v.video_id} item={v} platform="youtube" />)
            }
          </div>

          {/* TikTok / Instagram top 3 */}
          <div>
            <div className="highlight-group-label">🎵📸 TikTok / Instagram</div>
            {social_top.length === 0
              ? <div className="highlight-card highlight-card--empty"><div className="highlight-empty-msg">Nessun dato</div></div>
              : social_top.map(v => <HighlightVideoCard key={v.video_id} item={v} platform={v.platform} />)
            }
          </div>

          {/* Top commenti */}
          <div>
            <div className="highlight-group-label">💬 Commenti da monitorare</div>
            {comments_top.length === 0
              ? <div className="highlight-card highlight-card--empty"><div className="highlight-empty-msg">Nessun dato</div></div>
              : comments_top.map((c, i) => <HighlightCommentCard key={i} item={c} />)
            }
          </div>
        </div>
      )}

      {/* Row 2: segnali piattaforme */}
      <div className="highlights-grid-4">
        <HighlightSignalCard label="Reddit" item={reddit_top}    source="reddit" />
        <HighlightSignalCard label="X / Twitter" item={twitter_top} source="twitter" />
        <HighlightSignalCard label="Pinterest" item={pinterest_top} source="pinterest" />
        <HighlightSignalCard label="News" item={news_top}       source="news" />
      </div>
    </div>
  );
}

// ── Keyword Chart component ────────────────────────────────────────────────────

function KeywordChart({ keywords }) {
  const [selectedKw, setSelectedKw]   = useState('');
  const [inputKw,    setInputKw]      = useState('');
  const [hours,      setHours]        = useState(168);

  const kwToFetch = selectedKw || inputKw.trim();

  const { data: series = [], isFetching } = useQuery({
    queryKey:  ['kw-timeseries', kwToFetch, hours],
    queryFn:   () => fetchKeywordTimeseries(kwToFetch, hours),
    enabled:   kwToFetch.length > 0,
    staleTime: 5 * 60_000,
  });

  const maxVal = Math.max(...series.map(p => p.total), 1);

  return (
    <div>
      <div className="section-heading" style={{ marginTop: 24 }}>
        📈 Trend keyword nel tempo
      </div>
      <div className="card" style={{ padding: '16px' }}>
        {/* Controlli */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
          <select
            value={selectedKw}
            onChange={e => { setSelectedKw(e.target.value); setInputKw(''); }}
            style={{ flex: '1 1 160px', background: 'var(--surface-alt, #1a1a1a)', color: 'var(--text)', border: '1px solid #333', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}
          >
            <option value="">— scegli keyword —</option>
            {keywords.map(k => (
              <option key={k.keyword} value={k.keyword}>{k.keyword}</option>
            ))}
          </select>

          <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>o scrivi:</span>

          <input
            type="text"
            placeholder="keyword libera…"
            value={inputKw}
            onChange={e => { setInputKw(e.target.value); setSelectedKw(''); }}
            onKeyDown={e => e.key === 'Enter' && setInputKw(e.target.value)}
            style={{ flex: '1 1 140px', background: 'var(--surface-alt, #1a1a1a)', color: 'var(--text)', border: '1px solid #333', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}
          />

          <select
            value={hours}
            onChange={e => setHours(Number(e.target.value))}
            style={{ background: 'var(--surface-alt, #1a1a1a)', color: 'var(--text)', border: '1px solid #333', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}
          >
            <option value={24}>24h</option>
            <option value={48}>48h</option>
            <option value={168}>7 giorni</option>
            <option value={336}>14 giorni</option>
            <option value={720}>30 giorni</option>
          </select>
        </div>

        {/* Grafico */}
        {!kwToFetch ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
            Seleziona o digita una keyword per visualizzare il trend.
          </div>
        ) : isFetching ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>Caricamento…</div>
        ) : series.length === 0 ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
            Nessun dato per <b>{kwToFetch}</b> nelle ultime {hours}h.
          </div>
        ) : (
          <div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 80, overflowX: 'auto' }}>
              {series.map(({ hour_bucket, total }) => {
                const barH = Math.max(3, Math.round((total / maxVal) * 72));
                return (
                  <div
                    key={hour_bucket}
                    title={`${hour_bucket}: ${total}`}
                    style={{
                      minWidth: 8, flex: '0 0 auto',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                    }}
                  >
                    <div
                      style={{
                        width: 8, height: barH,
                        background: 'var(--accent, #7c3aed)',
                        borderRadius: '3px 3px 0 0',
                        opacity: 0.85,
                      }}
                    />
                  </div>
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{series[0]?.hour_bucket?.slice(5, 13)}</span>
              <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 600 }}>
                {series.reduce((s, p) => s + p.total, 0)} menzioni totali
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{series[series.length - 1]?.hour_bucket?.slice(5, 13)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: alerts24 = [] } = useQuery({
    queryKey: ['alerts', 24],
    queryFn: () => fetchAlerts(24, 50),
    staleTime: 2 * 60_000,
  });

  const { data: alerts168 = [] } = useQuery({
    queryKey: ['alerts', 168],
    queryFn: () => fetchAlerts(168, 200),
    staleTime: 5 * 60_000,
  });

  const { data: keywords = [] } = useQuery({
    queryKey: ['keywords', 168],
    queryFn: () => fetchKeywords(168, 15),
    staleTime: 5 * 60_000,
  });

  const { data: convergences = [] } = useQuery({
    queryKey: ['convergences', 48],
    queryFn: () => fetchConvergences(48, 2),
    staleTime: 2 * 60_000,
  });

  const { data: blacklist = [] } = useQuery({
    queryKey: ['blacklist'],
    queryFn: fetchBlacklist,
    staleTime: 10 * 60_000,
  });

  const { data: schedule = [] } = useQuery({
    queryKey: ['schedule'],
    queryFn: fetchSchedule,
    staleTime: 30 * 60_000,
  });

  const { data: alertsTimeline = [] } = useQuery({
    queryKey: ['alerts-timeline'],
    queryFn: () => fetchAlertsTimeline(14),
    staleTime: 10 * 60_000,
  });

  const { data: keywordSourcesMap = {} } = useQuery({
    queryKey: ['keyword-sources'],
    queryFn: () => fetchKeywordSources(168, 15),
    staleTime: 10 * 60_000,
  });

  const { data: highlights } = useQuery({
    queryKey: ['highlights'],
    queryFn: fetchHighlights,
    staleTime: 5 * 60_000,
  });

  const activeModules = schedule.filter(j => j.active).length;
  const totalModules  = schedule.length;
  const firstInactive = schedule.find(j => !j.active);
  const moduleSub     = firstInactive
    ? `${firstInactive.name.split(' ')[0]} disabilitato`
    : 'tutti attivi';

  const topKeywords = [...keywords]
    .sort((a, b) => (b.total_mentions ?? 0) - (a.total_mentions ?? 0))
    .slice(0, 10);

  return (
    <>
      <Topbar title="🏠 Dashboard" />
      <main className="page-content">

        {/* ── KPI strip ──────────────────────────────── */}
        <div className="kpi-grid-4">
          <KpiCard
            icon="🔔"
            label="ALERT OGGI"
            value={alerts24.length}
            sub={`ultimi 7 giorni: ${alerts168.length}`}
          />
          <KpiCard
            icon="🏷️"
            label="KEYWORDS ATTIVE"
            value={keywords.length}
            sub={`${blacklist.length} in blacklist`}
          />
          <KpiCard
            icon="🔗"
            label="CONVERGENZE 48H"
            value={convergences.length}
            sub="2+ fonti simultanee"
            tooltip={CONV_TOOLTIP}
          />
          <KpiCard
            icon="⚙️"
            label="MODULI ATTIVI"
            value={totalModules ? `${activeModules}/${totalModules}` : '—'}
            sub={moduleSub}
          />
        </div>

        {/* ── Highlights ──────────────────────────────── */}
        <HighlightsSection data={highlights} />

        {/* ── Alert recenti ───────────────────────────── */}
        <div className="section-heading">
          🔥 Alert recenti — Cross-Signal &amp; Convergenze
          <InfoTooltip text={ALERT_TOOLTIP} />
        </div>
        <div className="card">
          {alerts168.length === 0 && convergences.length === 0 ? (
            <EmptyState message="Nessun alert o convergenza registrata. Le velocity alerts appaiono quando una keyword supera le soglie configurate." />
          ) : alerts168.length > 0 ? (
            <>
              {alerts24.length === 0 && (
                <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                  Nessun alert nelle ultime 24h — mostro gli ultimi 7 giorni
                </p>
              )}
              <div className="alert-list">
                {(alerts24.length > 0 ? alerts24 : alerts168).slice(0, 12).map(a => (
                  <AlertItem key={a.id} alert={a} />
                ))}
              </div>
            </>
          ) : (
            <>
              <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                Nessun velocity alert recente — keyword attive su più fonti (convergenze 48h)
              </p>
              <div className="alert-list">
                {convergences.slice(0, 12).map(c => (
                  <ConvergenceItem key={c.keyword} item={c} />
                ))}
              </div>
            </>
          )}
        </div>

        {/* ── Alert Timeline ──────────────────────────── */}
        <AlertTimeline data={alertsTimeline} />

        {/* ── Top Keywords ────────────────────────────── */}
        <div className="section-heading" style={{ marginTop: 20 }}>
          📊 Top Keyword — Ultimi 7 giorni
          <InfoTooltip text={KW_TOOLTIP} />
        </div>
        <div className="card">
          {topKeywords.length === 0 ? (
            <EmptyState message="Nessuna keyword registrata negli ultimi 7 giorni." />
          ) : (
            <table className="kw-rank-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>KEYWORD</th>
                  <th>MENZIONI</th>
                  <th>FONTI</th>
                  <th>PIATTAFORME</th>
                  <th>ULTIMA MENZIONE</th>
                </tr>
              </thead>
              <tbody>
                {topKeywords.map((kw, i) => (
                  <KeywordRow
                    key={kw.keyword}
                    rank={i + 1}
                    kw={kw}
                    sourcesDetail={keywordSourcesMap[kw.keyword]}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ── Keyword Chart ────────────────────────────── */}
        <KeywordChart keywords={topKeywords} />

      </main>
    </>
  );
}
