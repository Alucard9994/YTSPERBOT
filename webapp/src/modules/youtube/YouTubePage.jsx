import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchOutperformer,
  fetchCompetitorVideos,
  fetchCompetitors,
  fetchCommentKeywords,
  fetchCommentIntel,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import Badge from '../../components/Badge.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtN(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function fmtDuration(s) {
  if (!s) return null;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, '0');
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${sec}`;
  return `${m}:${sec}`;
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

function growthColor(pct) {
  if (pct >= 10) return 'var(--accent)';
  if (pct >= 5)  return 'var(--orange)';
  if (pct >= 1)  return 'var(--yellow)';
  if (pct >= 0)  return 'var(--green)';
  return 'var(--text-dim)';
}
function growthBg(pct) {
  if (pct >= 10) return 'rgba(233,69,96,.18)';
  if (pct >= 5)  return 'rgba(249,115,22,.18)';
  if (pct >= 1)  return 'rgba(234,179,8,.18)';
  if (pct >= 0)  return 'rgba(34,197,94,.18)';
  return 'rgba(120,120,140,.12)';
}

function inferVideoType(title) {
  const t = (title || '').toLowerCase();
  if (t.includes('#shorts') || t.includes('#short') || t.includes(' short')) return 'short';
  return 'long';
}

function kwBadgeStyle(kw) {
  const colors = [
    { bg: 'rgba(168,85,247,.22)',   color: '#c084fc' },
    { bg: 'rgba(233,69,96,.22)',    color: '#f87171' },
    { bg: 'rgba(34,197,94,.2)',     color: '#4ade80' },
    { bg: 'rgba(96,165,250,.2)',    color: '#93c5fd' },
    { bg: 'rgba(249,115,22,.2)',    color: '#fdba74' },
    { bg: 'rgba(234,179,8,.2)',     color: '#fde047' },
  ];
  let s = 0;
  for (const c of (kw || '')) s = (s * 31 + c.charCodeAt(0)) & 0xff;
  return colors[s % colors.length];
}

/** Pick 1-2 deterministic "category" tags for a comment keyword */
const CTAG_POOL = [
  { label: 'richiesta video', color: 'blue' },
  { label: 'curiosità 🔍',   color: 'purple' },
  { label: 'shock',          color: 'purple' },
  { label: 'paura 😨',       color: 'purple' },
  { label: 'suggerimento',   color: 'blue' },
  { label: 'coinvolgimento', color: 'blue' },
  { label: 'domanda',        color: 'blue' },
  { label: 'entusiasmo ✨',  color: 'purple' },
];
function cTags(keyword) {
  let s = 0;
  for (const c of (keyword || '')) s = (s * 13 + c.charCodeAt(0)) & 0xff;
  return [CTAG_POOL[s % CTAG_POOL.length], CTAG_POOL[(s + 3) % CTAG_POOL.length]];
}

// ── shared ────────────────────────────────────────────────────────────────────

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

// ── Outperformer tab ──────────────────────────────────────────────────────────

function OutperformerCard({ v }) {
  const isShort = v.video_type === 'short';
  const ytUrl   = `https://www.youtube.com/watch?v=${v.video_id}`;
  const dur     = fmtDuration(v.duration_seconds);
  const avgView = v.avg_views ? fmtN(v.avg_views) : null;

  return (
    <div className="yt-out-card">
      {/* left icon */}
      <div className="yt-out-icon-box">
        <span style={{ fontSize: 22 }}>{isShort ? '📱' : '🎬'}</span>
      </div>

      {/* body */}
      <div className="yt-out-body">
        <div className="yt-out-badge-row">
          <Badge variant={isShort ? 'short' : 'long'}>{isShort ? 'SHORT' : 'LONG'}</Badge>
        </div>
        <div className="yt-out-title">{v.title}</div>
        <div className="yt-out-meta">
          {v.channel_name}
          {v.subscribers ? ` · ${fmtN(v.subscribers)} iscritti` : ''}
          {dur            ? ` · durata ${dur}` : ''}
          {v.published_at ? ` · ${timeAgo(v.published_at)}` : ''}
        </div>
        <div className="yt-out-stats">
          Views: <strong>{fmtN(v.views)}</strong>
          {avgView != null && (
            <> · Media canale: <strong>{avgView}</strong></>
          )}
        </div>
      </div>

      {/* right: multipliers + button */}
      <div className="yt-out-right">
        {v.multiplier_avg != null && (
          <div className="yt-mult-row">
            <span className="yt-mult-label">vs views medie</span>
            <span className="yt-mult-green">{v.multiplier_avg.toFixed(1)}x</span>
          </div>
        )}
        {v.multiplier_subs != null && (
          <div className="yt-mult-row">
            <span className="yt-mult-label">vs iscritti</span>
            <span className="yt-mult-blue">{v.multiplier_subs.toFixed(1)}x</span>
          </div>
        )}
        <button
          className="yt-trascrizione-btn"
          onClick={() => window.open(ytUrl, '_blank')}
        >
          📄 Trascrizione
        </button>
      </div>
    </div>
  );
}

function OutperformerSection({ label, videos }) {
  if (!videos.length) return null;
  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <div className="yt-section-head">{label} ({videos.length})</div>
      <div>
        {videos.map(v => <OutperformerCard key={v.video_id} v={v} />)}
      </div>
    </section>
  );
}

// ── Competitor tab ────────────────────────────────────────────────────────────

function ChannelRow({ ch, vPerWeek }) {
  const pct = ch.growth_pct ?? 0;
  return (
    <div className="yt-channel-row">
      <div className="yt-channel-avatar">📺</div>
      <div className="yt-channel-info">
        <div className="yt-channel-name">{ch.channel_name}</div>
        <div className="yt-channel-meta">
          {fmtN(ch.subscribers_now)} iscritti
          {vPerWeek > 0 && ` · ${vPerWeek} video/settimana`}
        </div>
      </div>
      <span className="vel-pill" style={{ color: growthColor(pct), background: growthBg(pct), flexShrink: 0 }}>
        {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%
      </span>
    </div>
  );
}

function CompetitorVideoItem({ v }) {
  const type    = inferVideoType(v.title);
  const isShort = type === 'short';
  const kw      = v.matched_keyword;
  const kwStyle = kw ? kwBadgeStyle(kw) : null;
  return (
    <div className="yt-video-item" onClick={() => window.open(`https://www.youtube.com/watch?v=${v.video_id}`, '_blank')}>
      <div className="yt-video-badges">
        <Badge variant={isShort ? 'short' : 'long'}>{isShort ? 'SHORT' : 'LONG'}</Badge>
      </div>
      <div className="yt-video-title">{v.title}</div>
      <div className="yt-video-meta">{v.channel_name} · {timeAgo(v.detected_at)}</div>
      {kw && (
        <span className="yt-kw-badge" style={{ background: kwStyle.bg, color: kwStyle.color }}>
          🎫 {kw}
        </span>
      )}
    </div>
  );
}

function CompetitorTab({ competitors, competitorVideos, compVideos7d, loading }) {
  const vCountMap = {};
  for (const v of compVideos7d) {
    vCountMap[v.channel_name] = (vCountMap[v.channel_name] || 0) + 1;
  }
  return (
    <div className="yt-comp-grid">
      <div className="card">
        <div className="trends-card-title">
          📺 CRESCITA ISCRITTI (7 GIORNI)
          <InfoTooltip text="Crescita % iscritti confrontando il primo e l'ultimo valore registrato negli ultimi 8 giorni." />
        </div>
        {loading ? (
          <p className="muted">Caricamento…</p>
        ) : competitors.length === 0 ? (
          <EmptyState icon="📺" message="Nessun canale competitor con dati iscritti registrati." />
        ) : (
          <div>
            {competitors.map(ch => (
              <ChannelRow key={ch.channel_id ?? ch.channel_name} ch={ch} vPerWeek={vCountMap[ch.channel_name] || 0} />
            ))}
          </div>
        )}
      </div>
      <div className="card">
        <div className="trends-card-title">🎬 NUOVI VIDEO (48H)</div>
        {loading ? (
          <p className="muted">Caricamento…</p>
        ) : competitorVideos.length === 0 ? (
          <EmptyState icon="🎬" message="Nessun nuovo video competitor nelle ultime 48 ore." />
        ) : (
          <div className="yt-video-list">
            {competitorVideos.map(v => <CompetitorVideoItem key={v.id ?? v.video_id} v={v} />)}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Commenti Intelligence tab ─────────────────────────────────────────────────

const CATEGORY_META = {
  richiesta_video:          { label: 'richiesta video',  color: 'blue'   },
  domanda_fonte:            { label: 'domanda fonte',    color: 'blue'   },
  richiesta_approfondimento:{ label: 'approfondimento',  color: 'blue'   },
  suggerimento_topic:       { label: 'suggerimento',     color: 'blue'   },
  paura:                    { label: 'paura 😨',         color: 'purple' },
  curiosita:                { label: 'curiosità 🔍',     color: 'purple' },
  shock:                    { label: 'shock',            color: 'purple' },
  coinvolgimento:           { label: 'coinvolgimento ✋', color: 'purple' },
};

function categoryTag(cat) {
  return CATEGORY_META[cat] ?? cTags(cat ?? '')[0];
}

/** Group flat comment rows into per-video buckets */
function groupByVideo(comments) {
  const map = {};
  for (const c of comments) {
    const key = c.video_id ?? c.video_title ?? 'unknown';
    if (!map[key]) map[key] = { video_id: c.video_id, video_title: c.video_title, channel_name: c.channel_name, comments: [] };
    map[key].comments.push(c);
  }
  return Object.values(map);
}

function CommentItem({ c }) {
  const isHot = (c.likes ?? 0) >= 100;
  return (
    <div className="yt-comment-item">
      <div className="yt-comment-text">{c.comment_text}</div>
      <div className="yt-comment-footer">
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>👍 {(c.likes ?? 0).toLocaleString('it-IT')} like</span>
        {isHot && <span className="yt-alta-rilevanza">🔥 Alta rilevanza</span>}
      </div>
    </div>
  );
}

function VideoCommentCard({ group }) {
  const ytUrl    = group.video_id ? `https://www.youtube.com/watch?v=${group.video_id}` : null;
  // Unique categories for this video
  const cats = [...new Set(group.comments.map(c => c.category).filter(Boolean))].slice(0, 3);
  // Show top N comments sorted by likes
  const top = [...group.comments].sort((a, b) => (b.likes ?? 0) - (a.likes ?? 0)).slice(0, 5);

  return (
    <div className="yt-comment-group">
      <div className="yt-comment-group-header">
        <span
          className="yt-comment-group-title"
          style={{ cursor: ytUrl ? 'pointer' : 'default' }}
          onClick={() => ytUrl && window.open(ytUrl, '_blank')}
        >
          {group.video_title ?? group.video_id ?? '—'}
          {ytUrl && <span style={{ marginLeft: 6, opacity: .5, fontSize: 12 }}>↗</span>}
        </span>
        <div className="yt-comment-group-tags">
          {cats.map((cat, i) => {
            const meta = categoryTag(cat);
            return <span key={i} className={`yt-ctag yt-ctag-${meta.color}`}>{meta.label}</span>;
          })}
        </div>
        <span className="yt-comment-group-count">
          {group.comments.length} commenti rilevanti · {group.channel_name}
        </span>
      </div>
      <div className="yt-comment-list">
        {top.map(c => <CommentItem key={c.id} c={c} />)}
      </div>
    </div>
  );
}

function CommentIntelligenceTab({ commentIntel, commentKeywords, loading }) {
  const groups      = groupByVideo(commentIntel);
  const totalComments = commentIntel.length;
  const hotComments = commentIntel.filter(c => (c.likes ?? 0) >= 100).length;

  return (
    <>
      <div className="kpi-grid-3">
        <KpiCard icon="💬" label="VIDEO ANALIZZATI"  value={groups.length}   sub="Con commenti classificati" />
        <KpiCard icon="📊" label="COMMENTI SALVATI"  value={totalComments}   sub="Ultimi 7 giorni" />
        <KpiCard icon="🔥" label="ALTA RILEVANZA"    value={hotComments}     sub="≥100 like" />
      </div>

      {groups.length > 0 ? (
        <div>
          {groups.map((g, i) => <VideoCommentCard key={i} group={g} />)}
        </div>
      ) : loading ? (
        <p className="muted" style={{ marginTop: 20 }}>Caricamento…</p>
      ) : (
        <EmptyState icon="💬" message="Nessun commento salvato ancora. Il modulo salverà i commenti al prossimo ciclo di analisi competitor." />
      )}
    </>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function YouTubePage() {
  const [tab, setTab] = useState('outperformer');

  const { data: outperformer = [], isLoading: loadingOut } = useQuery({
    queryKey: ['outperformer'],
    queryFn: () => fetchOutperformer(30, 50),
    staleTime: 5 * 60_000,
  });

  // 48h competitor videos (for "NUOVI VIDEO" col + 24h KPI)
  const { data: competitorVideos = [], isLoading: loadingComp } = useQuery({
    queryKey: ['competitor-videos', 48],
    queryFn: () => fetchCompetitorVideos(48, 50),
    staleTime: 5 * 60_000,
  });

  // 7-day competitor videos (for video/week frequency)
  const { data: compVideos7d = [] } = useQuery({
    queryKey: ['competitor-videos', 168],
    queryFn: () => fetchCompetitorVideos(168, 200),
    staleTime: 10 * 60_000,
  });

  // Channel subscriber growth (8-day window)
  const { data: competitors = [], isLoading: loadingChannels } = useQuery({
    queryKey: ['competitors'],
    queryFn: fetchCompetitors,
    staleTime: 10 * 60_000,
  });

  const { data: commentKeywords = [], isLoading: loadingCom } = useQuery({
    queryKey: ['comment-keywords'],
    queryFn: () => fetchCommentKeywords(168),
    staleTime: 5 * 60_000,
  });

  const { data: commentIntel = [], isLoading: loadingIntel } = useQuery({
    queryKey: ['comment-intel'],
    queryFn: () => fetchCommentIntel(168),
    staleTime: 5 * 60_000,
  });

  const shorts = outperformer.filter(v => v.video_type === 'short');
  const longs  = outperformer.filter(v => v.video_type !== 'short');

  // 24h competitor video count for KPI
  const now = Date.now();
  const comp24h = competitorVideos.filter(v => {
    const d = new Date(String(v.detected_at || '').replace(' ', 'T'));
    return !isNaN(d) && (now - d.getTime()) < 24 * 3_600_000;
  }).length;

  const TABS = [
    { key: 'outperformer', label: `🚀 Outperformer` },
    { key: 'competitor',   label: `📺 Competitor` },
    { key: 'comments',     label: `💬 Commenti Intelligence` },
  ];

  return (
    <>
      <Topbar title="🎬 YouTube" />
      <main className="page-content">

        {/* ── KPI strip (above tabs, always visible) ── */}
        <div className="kpi-grid-3">
          <KpiCard icon="🎬" label="LONG VIDEO OUTPERFORMER" value={longs.length}  sub="Ultimi 30 giorni" />
          <KpiCard icon="📱" label="SHORT OUTPERFORMER"      value={shorts.length} sub="Ultimi 30 giorni" />
          <KpiCard icon="🆕" label="NUOVI VIDEO COMPETITOR"  value={comp24h}       sub="Nelle ultime 24h" />
        </div>

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

        {/* ── Outperformer ── */}
        {tab === 'outperformer' && (
          <>
            {/* Multiplier legend */}
            <div className="yt-mult-legend">
              <span className="yt-legend-item">
                <span className="tooltip-trigger">i</span>
                <span><span style={{ color: 'var(--green)', fontWeight: 700 }}>vs views medie</span> = views ÷ media canale</span>
              </span>
              <span className="yt-legend-item">
                <span className="tooltip-trigger">i</span>
                <span><span style={{ color: 'var(--blue)', fontWeight: 700 }}>vs iscritti</span> = views ÷ iscritti</span>
              </span>
            </div>

            {loadingOut ? (
              <p className="muted">Caricamento…</p>
            ) : outperformer.length === 0 ? (
              <EmptyState icon="▶️" message="Nessun video outperformer rilevato negli ultimi 30 giorni." />
            ) : (
              <>
                <OutperformerSection label="🎬 VIDEO LUNGHI"    videos={longs}  />
                <OutperformerSection label="📱 YOUTUBE SHORTS" videos={shorts} />
              </>
            )}
          </>
        )}

        {/* ── Competitor ── */}
        {tab === 'competitor' && (
          <CompetitorTab
            competitors={competitors}
            competitorVideos={competitorVideos}
            compVideos7d={compVideos7d}
            loading={loadingComp || loadingChannels}
          />
        )}

        {/* ── Commenti Intelligence ── */}
        {tab === 'comments' && (
          <CommentIntelligenceTab
            commentIntel={commentIntel}
            commentKeywords={commentKeywords}
            loading={loadingCom || loadingIntel}
          />
        )}

      </main>
    </>
  );
}
