import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchRedditPosts,
  fetchRedditAlerts,
  fetchRedditKeywordCounts,
  fetchConfigLists,
  addConfigListItem,
  removeConfigListItem,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InlineListManager from '../../components/InlineListManager.jsx';

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

function alertTypeBadge(type) {
  const map = {
    reddit_apify_trend:    { label: '📈 Velocity',      bg: 'rgba(233,69,96,.18)',   color: 'var(--accent)' },
    reddit_hot_post:       { label: '🔥 Hot Post',      bg: 'rgba(249,115,22,.18)',  color: 'var(--orange)' },
    reddit_cross_signal:   { label: '🔀 Cross-Signal',  bg: 'rgba(139,92,246,.18)',  color: '#a78bfa' },
  };
  return map[type] || { label: type, bg: 'rgba(120,120,140,.14)', color: 'var(--text-dim)' };
}

function upvotesColor(n) {
  if (n >= 1000) return 'var(--accent)';
  if (n >= 300)  return 'var(--orange)';
  if (n >= 100)  return 'var(--yellow)';
  return 'var(--text-dim)';
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

function PostCard({ post }) {
  const upvotes = post.upvotes ?? 0;
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          minWidth: 52, textAlign: 'center',
          borderRadius: 8, padding: '6px 4px',
          background: 'rgba(120,120,140,.10)',
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: upvotesColor(upvotes) }}>
            {fmtK(upvotes)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>upvotes</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: 'var(--text)',
            lineHeight: 1.4, marginBottom: 4,
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {post.url
              ? <a href={post.url} target="_blank" rel="noopener noreferrer"
                   style={{ color: 'inherit', textDecoration: 'none' }}
                   onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
                   onMouseLeave={e => e.currentTarget.style.color = 'inherit'}>
                  {post.title || <em style={{ color: 'var(--text-dim)', fontWeight: 400 }}>📷 Immagine / Gallery</em>}
                </a>
              : post.title || <em style={{ color: 'var(--text-dim)', fontWeight: 400 }}>📷 Immagine / Gallery</em>}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 11, fontWeight: 600, color: 'var(--accent)',
              background: 'rgba(233,69,96,.12)', borderRadius: 4, padding: '2px 6px',
            }}>
              r/{post.subreddit}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              💬 {fmtK(post.num_comments)} commenti
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              🕐 {timeAgo(post.scraped_at)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertRow({ alert }) {
  const badge = alertTypeBadge(alert.alert_type);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 14px',
      borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        fontSize: 11, fontWeight: 600, borderRadius: 5, padding: '2px 8px',
        background: badge.bg, color: badge.color, whiteSpace: 'nowrap',
      }}>{badge.label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', flex: 1 }}>
        {alert.keyword}
      </span>
      {alert.velocity_pct != null && (
        <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700 }}>
          +{Math.round(alert.velocity_pct)}%
        </span>
      )}
      <span style={{ fontSize: 11, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
        {timeAgo(alert.sent_at)}
      </span>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

const HOUR_OPTIONS = [24, 48, 72, 168];
const TABS = ['Post', 'Alert', 'Keyword', 'Subreddit'];

export default function RedditPage() {
  const [hours, setHours]     = useState(48);
  const [tab, setTab]         = useState('Post');
  const [minUp, setMinUp]     = useState(0);
  const queryClient           = useQueryClient();

  const { data: posts = [],    isLoading: loadPosts }  = useQuery({ queryKey: ['reddit-posts', hours, minUp],    queryFn: () => fetchRedditPosts(hours, 30, minUp) });
  const { data: alerts = [],   isLoading: loadAlerts } = useQuery({ queryKey: ['reddit-alerts', hours],          queryFn: () => fetchRedditAlerts(hours) });
  const { data: kwCounts = [], isLoading: loadKw }     = useQuery({ queryKey: ['reddit-kw-counts', hours],      queryFn: () => fetchRedditKeywordCounts(hours) });
  const { data: configLists = {} }                     = useQuery({ queryKey: ['config-lists'],                  queryFn: fetchConfigLists, staleTime: 30_000 });

  const subreddits = configLists.subreddits ?? [];

  const addSubMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });
  const removeSubMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const isLoading = loadPosts || loadAlerts || loadKw;

  const totalUpvotes = posts.reduce((s, p) => s + (p.upvotes ?? 0), 0);
  const hotPosts     = posts.filter(p => (p.upvotes ?? 0) >= 100).length;

  return (
    <div className="page-wrapper">
      <Topbar title="Reddit" subtitle="Post virali, hot post, cross-subreddit signal" />

      {/* ── Controls ── */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <div className="btn-group">
          {HOUR_OPTIONS.map(h => (
            <button key={h}
              className={`btn btn-sm ${hours === h ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setHours(h)}>
              {h < 24 ? `${h}h` : h === 24 ? '24h' : h === 48 ? '48h' : h === 72 ? '3g' : '7g'}
            </button>
          ))}
        </div>
        {tab === 'Post' && (
          <label style={{ fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 6 }}>
            Min upvotes:
            <select value={minUp} onChange={e => setMinUp(Number(e.target.value))}
              style={{ fontSize: 12, background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 6, padding: '3px 8px' }}>
              {[0, 10, 50, 100, 500].map(v => <option key={v} value={v}>{v === 0 ? 'Tutti' : `≥${v}`}</option>)}
            </select>
          </label>
        )}
        {isLoading && <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Caricamento…</span>}
      </div>

      {/* ── KPIs ── */}
      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        <KpiCard icon="📄" label="Post trovati" value={posts.length} sub={`ultime ${hours}h`} />
        <KpiCard icon="🔥" label="Hot post" value={hotPosts} sub="≥100 upvotes" />
        <KpiCard icon="👍" label="Upvote totali" value={fmtK(totalUpvotes)} sub="nei post trovati" />
        <KpiCard icon="🚨" label="Alert generati" value={alerts.length} sub={`ultime ${hours}h`} />
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
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
            {t === 'Post' ? `Post (${posts.length})` : t === 'Alert' ? `Alert (${alerts.length})` : t === 'Keyword' ? `Keyword (${kwCounts.length})` : `Subreddit (${subreddits.length})`}
          </button>
        ))}
      </div>

      {/* ── Tab: Post ── */}
      {tab === 'Post' && (
        posts.length === 0
          ? <EmptyState icon="👽" message="Nessun post trovato nel periodo selezionato." />
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {posts.map(p => <PostCard key={p.post_id} post={p} />)}
            </div>
      )}

      {/* ── Tab: Alert ── */}
      {tab === 'Alert' && (
        alerts.length === 0
          ? <EmptyState icon="📭" message="Nessun alert Reddit nel periodo selezionato." />
          : <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
              {alerts.map((a, i) => <AlertRow key={i} alert={a} />)}
            </div>
      )}

      {/* ── Tab: Keyword ── */}
      {tab === 'Keyword' && (
        kwCounts.length === 0
          ? <EmptyState icon="🔍" message="Nessuna menzione keyword Reddit nel periodo." />
          : <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
              {kwCounts.map((kw, i) => {
                const maxTotal = kwCounts[0]?.total || 1;
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 16px', borderBottom: i < kwCounts.length - 1 ? '1px solid var(--border)' : 'none',
                  }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', minWidth: 120 }}>{kw.keyword}</span>
                    <div style={{ flex: 1, height: 6, background: 'var(--surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ height: '100%', borderRadius: 3, background: 'var(--accent)', width: `${Math.round((kw.total / maxTotal) * 100)}%` }} />
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', minWidth: 36, textAlign: 'right' }}>{fmtK(kw.total)}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 60, textAlign: 'right' }}>{timeAgo(kw.last_seen)}</span>
                  </div>
                );
              })}
            </div>
      )}

      {/* ── Tab: Subreddit ── */}
      {tab === 'Subreddit' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="trends-card-title" style={{ marginBottom: 12 }}>
              👽 SUBREDDIT MONITORATI
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 12 }}>
              Aggiungi o rimuovi subreddit da monitorare. Attivi al prossimo run del detector Reddit (ogni 42h).
            </p>
            <InlineListManager
              listKey="subreddits"
              items={subreddits}
              onAdd={(lk, v) => addSubMutation.mutate({ listKey: lk, value: v })}
              onRemove={(lk, v) => removeSubMutation.mutate({ listKey: lk, value: v })}
              placeholder="r/subreddit_name"
              isPending={addSubMutation.isPending || removeSubMutation.isPending}
              renderLabel={item => `r/${(item.value ?? item).replace(/^r\//i, '')}`}
              getUrl={item => `https://www.reddit.com/r/${(item.value ?? item).replace(/^r\//i, '')}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
