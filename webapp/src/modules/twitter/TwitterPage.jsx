import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchTopTweets,
  fetchTwitterViralAlerts,
  fetchTwitterKeywordCounts,
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

function alertTypeBadge(type) {
  const map = {
    twitter_trend:        { label: '📈 Velocity',      bg: 'rgba(233,69,96,.18)',   color: 'var(--accent)' },
    twitter_quote_storm:  { label: '💬 Quote Storm',   bg: 'rgba(249,115,22,.18)',  color: 'var(--orange)' },
    twitter_thread:       { label: '🧵 Thread',        bg: 'rgba(139,92,246,.18)',  color: '#a78bfa' },
    twitter_controversial:{ label: '🔥 Controversial', bg: 'rgba(234,179,8,.18)',   color: 'var(--yellow)' },
  };
  return map[type] || { label: type, bg: 'rgba(120,120,140,.14)', color: 'var(--text-dim)' };
}

function engagementColor(n) {
  if (n >= 500) return 'var(--accent)';
  if (n >= 200) return 'var(--orange)';
  if (n >= 50)  return 'var(--yellow)';
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

function TweetCard({ tweet }) {
  const engagement = tweet.engagement ?? (tweet.likes + tweet.retweets + tweet.quotes);
  const text = tweet.text || '';

  // Determina il tipo di alert più rilevante per il badge
  const isThread = tweet.replies > 0 && tweet.likes > 0 && tweet.replies / tweet.likes >= 0.8;
  const isControversial = !isThread && tweet.replies > 0 && tweet.likes > 0 && tweet.replies / tweet.likes >= 0.5;
  const isQuoteStorm = tweet.quotes > 0 && tweet.likes > 0 && tweet.quotes / tweet.likes >= 0.3;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* Header: author + badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {tweet.author_username && (
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)' }}>
            @{tweet.author_username}
          </span>
        )}
        {isThread      && <span style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'rgba(139,92,246,.18)', color: '#a78bfa' }}>🧵 Thread</span>}
        {isControversial && <span style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'rgba(234,179,8,.18)', color: 'var(--yellow)' }}>🔥 Controversial</span>}
        {isQuoteStorm  && <span style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'rgba(249,115,22,.18)', color: 'var(--orange)' }}>💬 Quote Storm</span>}
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)' }}>{timeAgo(tweet.scraped_at)}</span>
      </div>

      {/* Tweet text */}
      <div style={{
        fontSize: 13, color: 'var(--text)', lineHeight: 1.5,
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
      }}>
        {text}
      </div>

      {/* Stats + link */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: engagementColor(engagement) }}>
          📊 {fmtK(engagement)} eng
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>❤️ {fmtK(tweet.likes)}</span>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>🔁 {fmtK(tweet.retweets)}</span>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>💬 {fmtK(tweet.replies)}</span>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>🗣 {fmtK(tweet.quotes)}</span>
        {tweet.keyword && (
          <span style={{ fontSize: 11, color: 'var(--accent)', background: 'rgba(233,69,96,.1)', borderRadius: 4, padding: '1px 6px' }}>
            #{tweet.keyword}
          </span>
        )}
        {tweet.url && (
          <a href={tweet.url} target="_blank" rel="noopener noreferrer"
             style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>
            ↗ Vedi tweet
          </a>
        )}
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
const TABS = ['Tweet', 'Alert', 'Keyword'];

export default function TwitterPage() {
  const [hours, setHours] = useState(48);
  const [tab, setTab]     = useState('Tweet');

  const { data: tweets = [],   isLoading: loadTweets }  = useQuery({ queryKey: ['top-tweets', hours],       queryFn: () => fetchTopTweets(hours, 30) });
  const { data: alerts = [],   isLoading: loadAlerts }  = useQuery({ queryKey: ['twitter-viral', hours],    queryFn: () => fetchTwitterViralAlerts(hours) });
  const { data: kwCounts = [], isLoading: loadKw }      = useQuery({ queryKey: ['twitter-kw-counts', hours], queryFn: () => fetchTwitterKeywordCounts(hours) });

  const isLoading = loadTweets || loadAlerts || loadKw;

  const totalEng = tweets.reduce((s, t) => s + (t.engagement ?? 0), 0);
  const viralCount = tweets.filter(t => {
    const likes = t.likes ?? 0;
    if (likes === 0) return false;
    return (t.replies / likes >= 0.5) || (t.quotes / likes >= 0.3);
  }).length;

  return (
    <div className="page-wrapper">
      <Topbar title="Twitter / X" subtitle="Top tweet, quote storm, thread, controversial" />

      {/* ── Controls ── */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <div className="btn-group">
          {HOUR_OPTIONS.map(h => (
            <button key={h}
              className={`btn btn-sm ${hours === h ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setHours(h)}>
              {h === 24 ? '24h' : h === 48 ? '48h' : h === 72 ? '3g' : '7g'}
            </button>
          ))}
        </div>
        {isLoading && <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Caricamento…</span>}
      </div>

      {/* ── KPIs ── */}
      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        <KpiCard icon="🐦" label="Tweet trovati" value={tweets.length} sub={`ultime ${hours}h`} />
        <KpiCard icon="⚡" label="Viral signals" value={viralCount} sub="quote storm / thread / controversial" />
        <KpiCard icon="📊" label="Engagement tot." value={fmtK(totalEng)} sub="likes+RT+quotes" />
        <KpiCard icon="🚨" label="Alert generati" value={alerts.length} sub={`ultime ${hours}h`} />
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)' }}>
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
            {t === 'Tweet' ? `Tweet (${tweets.length})` : t === 'Alert' ? `Alert (${alerts.length})` : `Keyword (${kwCounts.length})`}
          </button>
        ))}
      </div>

      {/* ── Tab: Tweet ── */}
      {tab === 'Tweet' && (
        tweets.length === 0
          ? <EmptyState icon="🐦" message="Nessun tweet trovato nel periodo selezionato." />
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {tweets.map((t, i) => <TweetCard key={t.tweet_id || i} tweet={t} />)}
            </div>
      )}

      {/* ── Tab: Alert ── */}
      {tab === 'Alert' && (
        alerts.length === 0
          ? <EmptyState icon="📭" message="Nessun alert Twitter nel periodo selezionato." />
          : <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
              {alerts.map((a, i) => <AlertRow key={i} alert={a} />)}
            </div>
      )}

      {/* ── Tab: Keyword ── */}
      {tab === 'Keyword' && (
        kwCounts.length === 0
          ? <EmptyState icon="🔍" message="Nessuna menzione keyword Twitter nel periodo." />
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
    </div>
  );
}
