import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchOutperformer,
  fetchCompetitorVideos,
  fetchCompetitors,
  fetchSubscriberSparkline,
  fetchCompetitorVideosByKeyword,
  fetchCommentIntel,
  fetchCommentCategoryStats,
  fetchConfigLists,
  addConfigListItem,
  removeConfigListItem,
  fetchTranscript,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import Badge from '../../components/Badge.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import InlineListManager from '../../components/InlineListManager.jsx';
import Sparkline from '../../components/Sparkline.jsx';

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

// ── Transcript Modal ──────────────────────────────────────────────────────────

function TranscriptModal({ videoId, title, onClose }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['transcript', videoId],
    queryFn: () => fetchTranscript(videoId),
    retry: false,
    staleTime: 10 * 60_000,
  });

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--surface)',
        borderRadius: 12,
        padding: '20px 24px',
        width: '100%',
        maxWidth: 680,
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>📄 Trascrizione</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>{title}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: 'var(--text-dim)', lineHeight: 1, flexShrink: 0 }}>×</button>
        </div>

        {isLoading && <p style={{ color: 'var(--text-dim)', fontSize: 13, margin: 0 }}>⏳ Caricamento trascrizione…</p>}

        {isError && (
          <p style={{ color: '#f87171', fontSize: 13, margin: 0 }}>
            ❌ {error?.response?.data?.detail ?? 'Trascrizione non disponibile per questo video.'}
          </p>
        )}

        {data && (
          <>
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              {(data.length / 1000).toFixed(1)}k caratteri ·{' '}
              <a href={data.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>Apri video</a>
            </div>
            <div style={{
              overflowY: 'auto',
              flex: 1,
              fontSize: 13,
              lineHeight: 1.6,
              color: 'var(--text)',
              whiteSpace: 'pre-wrap',
              background: 'var(--surface-alt, #1a1a1a)',
              borderRadius: 8,
              padding: '12px 14px',
            }}>
              {data.transcript}
            </div>
            <button
              className="btn btn-ghost"
              style={{ alignSelf: 'flex-end', fontSize: 12 }}
              onClick={() => {
                navigator.clipboard.writeText(data.transcript);
              }}
            >
              📋 Copia testo
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Outperformer tab ──────────────────────────────────────────────────────────

function OutperformerCard({ v }) {
  const isShort = v.video_type === 'short';
  const ytUrl   = `https://www.youtube.com/watch?v=${v.video_id}`;
  const dur     = fmtDuration(v.duration_seconds);
  const avgView = v.avg_views ? fmtN(v.avg_views) : null;
  const [showTranscript, setShowTranscript] = useState(false);

  return (
    <>
      <div className="yt-out-card link-item" onClick={() => window.open(ytUrl, '_blank')} style={{ cursor: 'pointer' }}>
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
            onClick={(e) => { e.stopPropagation(); setShowTranscript(true); }}
          >
            📄 Trascrizione
          </button>
        </div>
      </div>

      {showTranscript && (
        <TranscriptModal
          videoId={v.video_id}
          title={v.title}
          onClose={() => setShowTranscript(false)}
        />
      )}
    </>
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

function OutperformerFiltered({ outperformer, loading }) {
  const [filter, setFilter] = useState('all'); // 'all' | 'short' | 'long'
  const byMult = arr => [...arr].sort((a, b) => (b.multiplier_avg ?? 0) - (a.multiplier_avg ?? 0));
  const shorts = outperformer.filter(v => v.video_type === 'short');
  const longs  = outperformer.filter(v => v.video_type !== 'short');
  const shown  = filter === 'short' ? shorts : filter === 'long' ? longs : outperformer;
  const shownShorts = byMult(shown.filter(v => v.video_type === 'short'));
  const shownLongs  = byMult(shown.filter(v => v.video_type !== 'short'));

  return (
    <>
      {/* Filter toggle */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {[
          { key: 'all',   label: `Tutti (${outperformer.length})` },
          { key: 'long',  label: `🎬 Long (${longs.length})` },
          { key: 'short', label: `📱 Shorts (${shorts.length})` },
        ].map(f => (
          <button
            key={f.key}
            className={`tab-btn${filter === f.key ? ' active' : ''}`}
            style={{ padding: '4px 14px', fontSize: 12 }}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

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

      {loading ? (
        <p className="muted">Caricamento…</p>
      ) : shown.length === 0 ? (
        <EmptyState icon="▶️" message="Nessun video outperformer per il filtro selezionato." />
      ) : (
        <>
          <OutperformerSection label="🎬 VIDEO LUNGHI"    videos={shownLongs}  />
          <OutperformerSection label="📱 YOUTUBE SHORTS" videos={shownShorts} />
        </>
      )}
    </>
  );
}

// ── Competitor tab ────────────────────────────────────────────────────────────

function ChannelRow({ ch, vPerWeek, sparkPoints }) {
  const pct         = ch.growth_pct ?? 0;
  const noHistory   = (ch.data_points ?? 1) < 2;
  const channelUrl  = ch.channel_id
    ? `https://www.youtube.com/channel/${ch.channel_id}`
    : `https://www.youtube.com/results?search_query=${encodeURIComponent(ch.channel_name)}`;
  return (
    <div className="yt-channel-row link-item" onClick={() => window.open(channelUrl, '_blank')} style={{ cursor: 'pointer' }}>
      <div className="yt-channel-avatar">📺</div>
      <div className="yt-channel-info">
        <div className="yt-channel-name link-title">{ch.channel_name} <span className="link-icon">↗</span></div>
        <div className="yt-channel-meta">
          {fmtN(ch.subscribers_now)} iscritti
          {vPerWeek > 0 && ` · ${vPerWeek} video/settimana`}
        </div>
      </div>
      {/* Sparkline iscritti */}
      {sparkPoints && sparkPoints.length >= 2 && (
        <div style={{ flexShrink: 0, marginRight: 8 }}>
          <Sparkline points={sparkPoints} width={64} height={24} color="auto" dotColor="auto" />
        </div>
      )}
      {noHistory ? (
        <span className="muted" style={{ fontSize: 12, flexShrink: 0 }}>dati insuff.</span>
      ) : (
        <span className="vel-pill" style={{ color: growthColor(pct), background: growthBg(pct), flexShrink: 0 }}>
          {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%
        </span>
      )}
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

function CompetitorTab({ competitors, competitorVideos, compVideos7d, videosByKeyword, sparklineMap, loading, channelsIt, channelsEn, onAddChannel, onRemoveChannel, chanPending }) {
  const [videoView, setVideoView] = useState('recent'); // 'recent' | 'keyword'
  const vCountMap = {};
  for (const v of compVideos7d) {
    vCountMap[v.channel_name] = (vCountMap[v.channel_name] || 0) + 1;
  }
  return (
    <>
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
                <ChannelRow
                  key={ch.channel_id ?? ch.channel_name}
                  ch={ch}
                  vPerWeek={vCountMap[ch.channel_name] || 0}
                  sparkPoints={sparklineMap[ch.channel_id] ?? []}
                />
              ))}
            </div>
          )}
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div className="trends-card-title" style={{ margin: 0 }}>🎬 VIDEO COMPETITOR</div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                className={`tab-btn${videoView === 'recent' ? ' active' : ''}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => setVideoView('recent')}
              >Recenti</button>
              <button
                className={`tab-btn${videoView === 'keyword' ? ' active' : ''}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => setVideoView('keyword')}
              >Per keyword</button>
            </div>
          </div>
          {loading ? (
            <p className="muted">Caricamento…</p>
          ) : videoView === 'recent' ? (
            competitorVideos.length === 0 ? (
              <EmptyState icon="🎬" message="Nessun nuovo video competitor nelle ultime 48 ore." />
            ) : (
              <div className="yt-video-list">
                {competitorVideos.map(v => <CompetitorVideoItem key={v.id ?? v.video_id} v={v} />)}
              </div>
            )
          ) : (
            videosByKeyword.length === 0 ? (
              <EmptyState icon="🎫" message="Nessun video con keyword matchata negli ultimi 7 giorni." />
            ) : (
              <div>
                {videosByKeyword.map(group => {
                  const kwStyle = kwBadgeStyle(group.keyword);
                  return (
                    <div key={group.keyword} style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span className="yt-kw-badge" style={{ background: kwStyle.bg, color: kwStyle.color, fontSize: 12 }}>
                          🎫 {group.keyword}
                        </span>
                        <span className="muted" style={{ fontSize: 11 }}>{group.count} video</span>
                      </div>
                      {group.videos.slice(0, 3).map(v => (
                        <CompetitorVideoItem key={v.video_id} v={v} />
                      ))}
                    </div>
                  );
                })}
              </div>
            )
          )}
        </div>
      </div>

      {/* ── Canali competitor manager ── */}
      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="trends-card-title" style={{ marginBottom: 10 }}>
            🇮🇹 CANALI COMPETITOR IT
          </div>
          <InlineListManager
            listKey="channels_it"
            items={channelsIt}
            onAdd={onAddChannel}
            onRemove={onRemoveChannel}
            placeholder="@handle o nome canale"
            isPending={chanPending}
            getUrl={item => `https://www.youtube.com/@${(item.value ?? item).replace(/^@/, '')}`}
          />
        </div>
        <div className="card">
          <div className="trends-card-title" style={{ marginBottom: 10 }}>
            🇬🇧 CANALI COMPETITOR EN
          </div>
          <InlineListManager
            listKey="channels_en"
            items={channelsEn}
            onAdd={onAddChannel}
            onRemove={onRemoveChannel}
            placeholder="@handle o nome canale"
            isPending={chanPending}
            getUrl={item => `https://www.youtube.com/@${(item.value ?? item).replace(/^@/, '')}`}
          />
        </div>
      </div>
    </>
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

/** Strip HTML tags and decode common HTML entities from YouTube comment text. */
function sanitizeComment(text) {
  if (!text) return '';
  return text
    .replace(/<[^>]*>/g, ' ')      // remove all HTML tags
    .replace(/&#39;/g,  "'")
    .replace(/&amp;/g,  '&')
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g,   '<')
    .replace(/&gt;/g,   '>')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g,    ' ')       // collapse extra whitespace from removed tags
    .trim();
}

function CommentItem({ c }) {
  const isHot = (c.likes ?? 0) >= 100;
  return (
    <div className="yt-comment-item">
      <div className="yt-comment-text">{sanitizeComment(c.comment_text)}</div>
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

const CAT_EMOJI = {
  richiesta_video: '🎬',
  domanda_fonte: '🔗',
  richiesta_approfondimento: '🔍',
  suggerimento_topic: '💡',
  paura: '😨',
  curiosita: '🧐',
  shock: '😲',
  coinvolgimento: '✋',
};

function CategoryBreakdown({ stats }) {
  if (!stats || stats.length === 0) return null;
  const total = stats.reduce((s, r) => s + r.count, 0);
  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="trends-card-title" style={{ marginBottom: 12 }}>
        📊 DISTRIBUZIONE SENTIMENT COMMENTI (7 GIORNI)
        <InfoTooltip text="Categorie assegnate dall'AI ai commenti salvati dai video competitor. Mostra cosa chiede/prova il pubblico." />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {stats.map(({ category, count }) => {
          const meta   = CATEGORY_META[category] ?? { label: category, color: 'blue' };
          const pct    = total > 0 ? Math.round((count / total) * 100) : 0;
          const emoji  = CAT_EMOJI[category] ?? '💬';
          const barCol = meta.color === 'purple' ? 'var(--accent)' : 'var(--blue)';
          return (
            <div key={category}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                <span style={{ color: 'var(--text)' }}>{emoji} {meta.label}</span>
                <span style={{ color: 'var(--text-dim)' }}>{count} ({pct}%)</span>
              </div>
              <div style={{ height: 5, background: 'var(--surface-alt, #222)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: barCol, borderRadius: 3, transition: 'width .4s' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CommentIntelligenceTab({ commentIntel, categoryStats, loading }) {
  const [activeCat, setActiveCat] = useState(null);

  // Filter comments and regroup based on active category
  const filtered = useMemo(() => {
    if (!activeCat) return commentIntel;
    return commentIntel.filter(c => c.category === activeCat);
  }, [commentIntel, activeCat]);

  const groups        = groupByVideo(filtered);
  const totalComments = commentIntel.length;
  const hotComments   = commentIntel.filter(c => (c.likes ?? 0) >= 100).length;

  return (
    <>
      <div className="kpi-grid-3">
        <KpiCard icon="💬" label="VIDEO ANALIZZATI"  value={groupByVideo(commentIntel).length} sub="Con commenti classificati" />
        <KpiCard icon="📊" label="COMMENTI SALVATI"  value={totalComments}                     sub="Ultimi 7 giorni" />
        <KpiCard icon="🔥" label="ALTA RILEVANZA"    value={hotComments}                       sub="≥100 like" />
      </div>

      <CategoryBreakdown stats={categoryStats} />

      {/* ── Category filter pills ── */}
      {categoryStats.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
          <button
            className={`yt-cat-pill${activeCat === null ? ' yt-cat-pill-active' : ''}`}
            onClick={() => setActiveCat(null)}
          >
            Tutti ({totalComments})
          </button>
          {categoryStats.map(({ category, count }) => {
            const emoji = CAT_EMOJI[category] ?? '💬';
            const meta  = CATEGORY_META[category] ?? { label: category };
            return (
              <button
                key={category}
                className={`yt-cat-pill${activeCat === category ? ' yt-cat-pill-active' : ''}`}
                onClick={() => setActiveCat(prev => prev === category ? null : category)}
              >
                {emoji} {meta.label} ({count})
              </button>
            );
          })}
        </div>
      )}

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
  const queryClient = useQueryClient();

  const { data: outperformer = [], isLoading: loadingOut } = useQuery({
    queryKey: ['outperformer'],
    queryFn: () => fetchOutperformer(30, 200),
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

  // Competitor videos grouped by keyword (7 days)
  const { data: videosByKeyword = [] } = useQuery({
    queryKey: ['competitor-videos-by-keyword'],
    queryFn: () => fetchCompetitorVideosByKeyword(7),
    staleTime: 10 * 60_000,
  });

  // Channel subscriber growth (8-day window)
  const { data: competitors = [], isLoading: loadingChannels } = useQuery({
    queryKey: ['competitors'],
    queryFn: fetchCompetitors,
    staleTime: 10 * 60_000,
  });

  // Sparkline data per channel
  const { data: sparklineRaw = [] } = useQuery({
    queryKey: ['subscriber-sparkline'],
    queryFn: () => fetchSubscriberSparkline(10),
    staleTime: 10 * 60_000,
  });
  const sparklineMap = useMemo(() => {
    const m = {};
    for (const ch of sparklineRaw) m[ch.channel_id] = ch.points;
    return m;
  }, [sparklineRaw]);

  const { data: categoryStats = [], isLoading: loadingCom } = useQuery({
    queryKey: ['comment-category-stats'],
    queryFn: () => fetchCommentCategoryStats(168),
    staleTime: 5 * 60_000,
  });

  const { data: configLists = {} } = useQuery({
    queryKey: ['config-lists'],
    queryFn: fetchConfigLists,
    staleTime: 30_000,
  });
  const channelsIt = configLists.channels_it ?? [];
  const channelsEn = configLists.channels_en ?? [];

  const addChannelMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });
  const removeChannelMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
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
          <OutperformerFiltered outperformer={outperformer} loading={loadingOut} />
        )}

        {/* ── Competitor ── */}
        {tab === 'competitor' && (
          <CompetitorTab
            competitors={competitors}
            competitorVideos={competitorVideos}
            compVideos7d={compVideos7d}
            videosByKeyword={videosByKeyword}
            sparklineMap={sparklineMap}
            loading={loadingComp || loadingChannels}
            channelsIt={channelsIt}
            channelsEn={channelsEn}
            onAddChannel={(lk, v) => addChannelMutation.mutate({ listKey: lk, value: v })}
            onRemoveChannel={(lk, v) => removeChannelMutation.mutate({ listKey: lk, value: v })}
            chanPending={addChannelMutation.isPending || removeChannelMutation.isPending}
          />
        )}

        {/* ── Commenti Intelligence ── */}
        {tab === 'comments' && (
          <CommentIntelligenceTab
            commentIntel={commentIntel}
            categoryStats={categoryStats}
            loading={loadingCom || loadingIntel}
          />
        )}

      </main>
    </>
  );
}
