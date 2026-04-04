import { useState, useEffect, useCallback } from 'react';
import Topbar from '../../components/Topbar.jsx';
import {
  fetchDiscoverySuggestions,
  acceptDiscoverySuggestion,
  rejectDiscoverySuggestion,
} from '../../api/client.js';

const TYPE_META = {
  tiktok_hashtag:    { label: 'TikTok Hashtag',   icon: '🎵', badgeClass: 'badge-purple', prefix: '#' },
  instagram_hashtag: { label: 'IG Hashtag',        icon: '📸', badgeClass: 'badge-blue',   prefix: '#' },
  subreddit:         { label: 'Subreddit',          icon: '👽', badgeClass: 'badge-orange',  prefix: 'r/' },
  keyword:           { label: 'Keyword',            icon: '🔑', badgeClass: 'badge-cyan',    prefix: '' },
};

const SOURCE_LABEL = {
  tiktok_caption:    'captions TikTok',
  instagram_caption: 'captions Instagram',
  reddit_post:       'post Reddit',
  twitter_tweet:     'tweet Twitter',
};

const STATUS_TABS = [
  { id: 'pending',  label: 'In attesa' },
  { id: 'accepted', label: 'Accettati' },
  { id: 'rejected', label: 'Rifiutati' },
  { id: 'all',      label: 'Tutti' },
];

const TYPE_FILTERS = [
  { id: 'all',               label: 'Tutti' },
  { id: 'tiktok_hashtag',    label: '🎵 TikTok' },
  { id: 'instagram_hashtag', label: '📸 Instagram' },
  { id: 'subreddit',         label: '👽 Subreddit' },
  { id: 'keyword',           label: '🔑 Keyword' },
];

export default function DiscoveryPage() {
  const [data, setData]           = useState({ suggestions: [], pending_count: 0 });
  const [filter, setFilter]       = useState('all');
  const [statusTab, setStatusTab] = useState('pending');
  const [loading, setLoading]     = useState(true);
  const [actioned, setActioned]   = useState({});

  const load = useCallback(() => {
    setLoading(true);
    fetchDiscoverySuggestions(statusTab)
      .then((d) => setData(d))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [statusTab]);

  useEffect(() => { load(); }, [load]);

  const handleAccept = async (id) => {
    try {
      await acceptDiscoverySuggestion(id);
      setActioned((p) => ({ ...p, [id]: 'accepted' }));
      setData((p) => ({
        ...p,
        pending_count: Math.max(0, p.pending_count - 1),
        suggestions: p.suggestions.map((s) => s.id === id ? { ...s, status: 'accepted' } : s),
      }));
    } catch (e) { console.error(e); }
  };

  const handleReject = async (id) => {
    try {
      await rejectDiscoverySuggestion(id);
      setActioned((p) => ({ ...p, [id]: 'rejected' }));
      setData((p) => ({
        ...p,
        pending_count: Math.max(0, p.pending_count - 1),
        suggestions: p.suggestions.map((s) => s.id === id ? { ...s, status: 'rejected' } : s),
      }));
    } catch (e) { console.error(e); }
  };

  const visible = data.suggestions.filter((s) =>
    filter === 'all' ? true : s.type === filter
  );

  const countPendingByType = (type) =>
    data.suggestions.filter((s) => s.type === type && s.status === 'pending').length;

  return (
    <>
      <Topbar
        title="Discovery"
        subtitle="Suggerimenti automatici da co-occorrenza nei dati scrappati"
      />
      <main className="page-content">

        {/* ── Top bar: pending badge + refresh ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {data.pending_count > 0 && (
              <span className="badge badge-red" style={{ fontSize: 13, padding: '4px 12px' }}>
                {data.pending_count} in attesa
              </span>
            )}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            {loading ? 'Carico…' : '↻ Aggiorna'}
          </button>
        </div>

        {/* ── Status tabs ── */}
        <div className="feed-filter-row" style={{ marginBottom: 10 }}>
          {STATUS_TABS.map((t) => (
            <button
              key={t.id}
              className={`feed-filter-btn ${statusTab === t.id ? 'active' : ''}`}
              onClick={() => setStatusTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Type filter ── */}
        <div className="feed-filter-row" style={{ marginBottom: 20 }}>
          {TYPE_FILTERS.map((t) => (
            <button
              key={t.id}
              className={`feed-filter-btn ${filter === t.id ? 'active' : ''}`}
              onClick={() => setFilter(t.id)}
            >
              {t.label}
              {t.id !== 'all' && countPendingByType(t.id) > 0 && (
                <span style={{ marginLeft: 5, opacity: 0.75 }}>({countPendingByType(t.id)})</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Content ── */}
        {loading ? (
          <p style={{ color: 'var(--text-muted)', padding: '24px 0' }}>Caricamento…</p>
        ) : visible.length === 0 ? (
          <div
            style={{
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: '32px 24px',
              textAlign: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 8 }}>🔍</div>
            <p style={{ margin: 0, fontSize: 14 }}>
              {statusTab === 'pending'
                ? 'Nessun suggerimento in attesa. Il discovery advisor gira ogni domenica.'
                : 'Nessun suggerimento per questo filtro.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {visible.map((s) => {
              const meta   = TYPE_META[s.type] || { label: s.type, icon: '?', badgeClass: 'badge-default', prefix: '' };
              const action = actioned[s.id] || s.status;
              const isDone = action === 'accepted' || action === 'rejected';

              return (
                <div
                  key={s.id}
                  style={{
                    background: 'var(--surface2)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 14,
                    opacity: isDone ? 0.5 : 1,
                    transition: 'opacity .2s',
                  }}
                >
                  {/* Type badge */}
                  <span className={`badge ${meta.badgeClass}`} style={{ flexShrink: 0, minWidth: 120 }}>
                    {meta.icon} {meta.label}
                  </span>

                  {/* Value */}
                  <span style={{ fontWeight: 600, color: '#fff', fontSize: 15, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {meta.prefix}{s.value}
                  </span>

                  {/* Score */}
                  <span style={{ background: 'var(--surface3)', border: '1px solid var(--border)', borderRadius: 20, padding: '2px 10px', fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                    {s.score}×
                  </span>

                  {/* Source */}
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', flexShrink: 0, minWidth: 120, textAlign: 'right' }}>
                    da {SOURCE_LABEL[s.source] || s.source}
                  </span>

                  {/* Actions */}
                  {action === 'accepted' ? (
                    <span className="badge badge-green" style={{ flexShrink: 0 }}>✓ Aggiunto</span>
                  ) : action === 'rejected' ? (
                    <span className="badge badge-default" style={{ flexShrink: 0 }}>✗ Rifiutato</span>
                  ) : (
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <button
                        className="btn btn-sm"
                        onClick={() => handleAccept(s.id)}
                        style={{ border: '1px solid var(--green)', background: 'rgba(34,197,94,.12)', color: 'var(--green)', fontWeight: 600 }}
                      >
                        ✓ Aggiungi
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleReject(s.id)}
                      >
                        ✗
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Footer info ── */}
        <p style={{ marginTop: 24, fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.7 }}>
          Analizza captions TikTok/Instagram, titoli post Reddit e tweet per trovare hashtag e subreddit
          co-occorrenti non ancora monitorati. Gira ogni domenica alle 07:00 UTC. ✓ Aggiungi aggiunge
          direttamente alla lista in Config &amp; Sistema.
        </p>

      </main>
    </>
  );
}
