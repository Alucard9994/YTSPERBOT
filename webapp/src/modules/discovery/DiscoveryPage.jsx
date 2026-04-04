import { useState, useEffect, useCallback } from 'react';
import {
  fetchDiscoverySuggestions,
  acceptDiscoverySuggestion,
  rejectDiscoverySuggestion,
} from '../../api/client.js';

const TYPE_META = {
  tiktok_hashtag:    { label: 'TikTok Hashtag',    icon: '🎵', badgeClass: 'badge-purple', prefix: '#' },
  instagram_hashtag: { label: 'Instagram Hashtag',  icon: '📸', badgeClass: 'badge-blue',   prefix: '#' },
  subreddit:         { label: 'Subreddit',           icon: '👽', badgeClass: 'badge-orange',  prefix: 'r/' },
  keyword:           { label: 'Keyword',             icon: '🔑', badgeClass: 'badge-cyan',    prefix: '' },
};

const SOURCE_LABEL = {
  tiktok_caption:    'da captions TikTok',
  instagram_caption: 'da captions Instagram',
  reddit_post:       'da post Reddit',
  twitter_tweet:     'da tweet Twitter',
};

const FILTER_TABS = [
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
  const [actioned, setActioned]   = useState({}); // id → 'accepted'|'rejected'

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
      setActioned((prev) => ({ ...prev, [id]: 'accepted' }));
      setData((prev) => ({
        ...prev,
        pending_count: Math.max(0, prev.pending_count - 1),
        suggestions: prev.suggestions.map((s) =>
          s.id === id ? { ...s, status: 'accepted' } : s
        ),
      }));
    } catch (e) {
      console.error(e);
    }
  };

  const handleReject = async (id) => {
    try {
      await rejectDiscoverySuggestion(id);
      setActioned((prev) => ({ ...prev, [id]: 'rejected' }));
      setData((prev) => ({
        ...prev,
        pending_count: Math.max(0, prev.pending_count - 1),
        suggestions: prev.suggestions.map((s) =>
          s.id === id ? { ...s, status: 'rejected' } : s
        ),
      }));
    } catch (e) {
      console.error(e);
    }
  };

  const visible = data.suggestions.filter((s) =>
    filter === 'all' ? true : s.type === filter
  );

  const countByType = (type) =>
    data.suggestions.filter((s) => s.type === type && s.status === 'pending').length;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#fff', margin: 0 }}>
            🔍 Discovery Advisor
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '4px 0 0' }}>
            Suggerimenti automatici scoperti per co-occorrenza nei dati scrappati
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {data.pending_count > 0 && (
            <span className="badge badge-red" style={{ fontSize: 13, padding: '4px 12px' }}>
              {data.pending_count} in attesa
            </span>
          )}
          <button
            className="btn-primary"
            onClick={load}
            disabled={loading}
            style={{ padding: '6px 16px', fontSize: 13 }}
          >
            {loading ? 'Carico…' : '↻ Aggiorna'}
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div className="feed-filter-row" style={{ marginBottom: 16 }}>
        {[
          { id: 'pending',  label: 'In attesa' },
          { id: 'accepted', label: 'Accettati' },
          { id: 'rejected', label: 'Rifiutati' },
          { id: 'all',      label: 'Tutti' },
        ].map((t) => (
          <button
            key={t.id}
            className={`feed-filter-btn ${statusTab === t.id ? 'active' : ''}`}
            onClick={() => setStatusTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Type filter tabs */}
      <div className="feed-filter-row" style={{ marginBottom: 20 }}>
        {FILTER_TABS.map((t) => (
          <button
            key={t.id}
            className={`feed-filter-btn ${filter === t.id ? 'active' : ''}`}
            onClick={() => setFilter(t.id)}
          >
            {t.label}
            {t.id !== 'all' && countByType(t.id) > 0 && (
              <span style={{ marginLeft: 5, opacity: 0.8 }}>({countByType(t.id)})</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <p style={{ color: 'var(--text-muted)', padding: 24 }}>Caricamento…</p>
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
          <p style={{ margin: 0 }}>
            {statusTab === 'pending'
              ? 'Nessun suggerimento in attesa. Il discovery advisor gira ogni domenica.'
              : 'Nessun suggerimento trovato per questo filtro.'}
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
                  opacity: isDone ? 0.55 : 1,
                  transition: 'opacity .2s',
                }}
              >
                {/* Type badge */}
                <span className={`badge ${meta.badgeClass}`} style={{ flexShrink: 0, minWidth: 110 }}>
                  {meta.icon} {meta.label}
                </span>

                {/* Value */}
                <span style={{ fontWeight: 600, color: '#fff', fontSize: 15, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {meta.prefix}{s.value}
                </span>

                {/* Score */}
                <span
                  style={{
                    background: 'var(--surface3)',
                    border: '1px solid var(--border)',
                    borderRadius: 20,
                    padding: '2px 10px',
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    flexShrink: 0,
                  }}
                >
                  {s.score}x
                </span>

                {/* Source */}
                <span style={{ fontSize: 11, color: 'var(--text-dim)', flexShrink: 0, minWidth: 120, textAlign: 'right' }}>
                  {SOURCE_LABEL[s.source] || s.source}
                </span>

                {/* Actions */}
                {action === 'accepted' ? (
                  <span className="badge badge-green" style={{ flexShrink: 0 }}>✓ Aggiunto</span>
                ) : action === 'rejected' ? (
                  <span className="badge badge-default" style={{ flexShrink: 0 }}>✗ Rifiutato</span>
                ) : (
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                    <button
                      onClick={() => handleAccept(s.id)}
                      style={{
                        padding: '4px 14px',
                        borderRadius: 6,
                        border: '1px solid var(--green)',
                        background: 'rgba(34,197,94,.12)',
                        color: 'var(--green)',
                        fontSize: 12,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        fontWeight: 600,
                      }}
                    >
                      ✓ Aggiungi
                    </button>
                    <button
                      onClick={() => handleReject(s.id)}
                      style={{
                        padding: '4px 14px',
                        borderRadius: 6,
                        border: '1px solid var(--border)',
                        background: 'transparent',
                        color: 'var(--text-muted)',
                        fontSize: 12,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}
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

      {/* Info footer */}
      <p style={{ marginTop: 24, fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6 }}>
        Il discovery advisor analizza i contenuti già scrappati (captions TikTok/Instagram, post Reddit, tweet) e suggerisce hashtag/subreddit/keyword che compaiono frequentemente ma non sono ancora monitorati.
        Gira automaticamente ogni domenica. Usa il pulsante ✓ Aggiungi per aggiungere direttamente alle liste in Config.
      </p>
    </div>
  );
}
