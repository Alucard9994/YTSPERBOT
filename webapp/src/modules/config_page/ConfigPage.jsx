import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchConfigParams,
  updateConfigParam,
  fetchConfigLists,
  addConfigListItem,
  removeConfigListItem,
  fetchBlacklist,
  addBlacklistItem,
  removeBlacklistItem,
  fetchSystemStatus,
  fetchSchedule,
  downloadBackup,
  restoreBackup,
  fetchLogs,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import Badge from '../../components/Badge.jsx';

// Descrizioni human-readable dei parametri (chiave → desc)
const PARAM_DESCRIPTIONS = {
  // YouTube Scraper
  'scraper.multiplier_threshold':       'Min moltiplicatore vs views medie (YouTube)',
  'scraper.min_views':                  'Views minime assolute per un video YouTube',
  'scraper.multiplier_subs_threshold':  'Min moltiplicatore vs iscritti (YouTube)',
  // Trend Detector
  'trend.velocity_threshold_longform':  '% velocity soglia RSS / Comments (long-form)',
  'trend.velocity_threshold_shortform': '% velocity soglia Twitter / Reddit (short-form)',
  'trend.min_mentions_to_track':        'Menzioni minime per tracciare una keyword',
  // Twitter / X
  'twitter.tweets_per_keyword':         'Tweet per keyword analizzati per run',
  // Reddit (Apify)
  'reddit.subreddits_per_run':          'Subreddit analizzati per run (Apify)',
  'reddit.posts_per_subreddit':         'Post per subreddit scaricati (Apify)',
  // Pinterest (Apify)
  'pinterest.keywords_per_run':         'Keyword Pinterest analizzate per run (Apify)',
  'pinterest.pins_per_keyword':         'Pin massimi per keyword (Apify)',
  // TikTok / Instagram (Apify)
  'apify.multiplier_threshold':         'Moltiplicatore outperformer TikTok / IG vs media',
  'apify.multiplier_threshold_followers': 'Moltiplicatore outperformer vs follower',
  'apify.min_followers':                'Follower minimi profili TikTok / IG',
  'apify.max_followers':                'Follower massimi profili TikTok / IG',
  'apify.tiktok_min_views':             'Views minime video TikTok (Apify)',
  'apify.instagram_min_views':          'Views minime reel Instagram (Apify)',
  'apify.new_profiles_per_platform':    'Nuovi profili da scoprire per piattaforma per run',
  'apify.profile_recheck_days':         'Giorni tra rianalisi di un profilo già noto',
  'apify.results_per_profile':          'Video / post scaricati per profilo',
  // News
  'news.velocity_threshold':            '% velocity soglia articoli news',
  // Cross-signal
  'cross_signal.min_sources':           'N° fonti minime per convergenza multi-piattaforma',
  // Subscriber
  'subscriber.growth_threshold':        '% crescita iscritti competitor (7 giorni)',
  // Priority
  'priority_score.min_score':           'Score minimo per inviare un alert (1-10)',
};

/**
 * Parametri che non ha senso modificare dalla UI perché richiedono un
 * riavvio del bot per avere effetto (scheduler intervals, switch scraper, ecc.).
 * Vanno modificati direttamente in config.yaml.
 */
const HIDDEN_PARAMS = new Set([
  // intervalli scheduler — richiedono riavvio
  'trend.check_interval_hours',
  'twitter.check_interval_hours',
  'news.check_interval_hours',
  'pinterest.check_interval_hours',
  'subscriber.check_interval_hours',
  'reddit.check_interval_hours',
  'competitor_monitor.check_interval_minutes',
  'google_trends.check_interval_hours',
  // switch modalità — richiedono riavvio
  'twitter.use_apify',
  'reddit.use_apify',
  'pinterest.use_apify',
  // tempi di esecuzione scraper
  'apify.run_interval_days',
  'apify.run_time',
]);

// ── Parametri ───────────────────────────────────────────────────────────────
function ParamRow({ param, onSave }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(param.value ?? '');

  function handleSave() {
    onSave(param.key, val);
    setEditing(false);
  }

  return (
    <div className="config-row">
      <div style={{ flex: 2 }}>
        <div className="config-label">{param.key}</div>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
          {PARAM_DESCRIPTIONS[param.key] ?? ''}
        </div>
      </div>
      {editing ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="config-input"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') { setEditing(false); setVal(param.value ?? ''); }
            }}
          />
          <button className="btn btn-primary btn-sm" onClick={handleSave}>Salva</button>
          <button className="btn btn-sm" onClick={() => { setEditing(false); setVal(param.value ?? ''); }}>Annulla</button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span className="config-value">{param.value ?? <span className="muted">—</span>}</span>
          <button className="btn btn-sm" onClick={() => setEditing(true)}>Modifica</button>
        </div>
      )}
    </div>
  );
}

// ── Schedule ────────────────────────────────────────────────────────────────
function ScheduleTab() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['schedule'],
    queryFn: fetchSchedule,
    staleTime: 60_000,
  });

  if (isLoading) return <p className="muted">Caricamento…</p>;
  if (jobs.length === 0) return <EmptyState icon="🕐" message="Nessun job trovato." />;

  return (
    <div className="card">
      {jobs.map((job, i) => (
        <div key={i} className="sched-item">
          <div
            className="sched-dot"
            style={{ background: job.active ? 'var(--success)' : 'var(--text-dim)' }}
            title={job.active ? 'Attivo' : 'Non attivo (credenziale mancante)'}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: 'var(--text)' }}>{job.name}</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-dim)', marginTop: 2 }}>{job.freq}</div>
          </div>
          {!job.active && <Badge variant="medium">Disabilitato</Badge>}
        </div>
      ))}
    </div>
  );
}

// ── Liste ────────────────────────────────────────────────────────────────────
function ListCard({ listKey, title, items, onAdd, onRemove }) {
  const [newVal, setNewVal] = useState('');

  function handleAdd() {
    if (!newVal.trim()) return;
    onAdd(listKey, newVal.trim());
    setNewVal('');
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-dim)', letterSpacing: '.8px' }}>
          {title}
        </div>
      </div>
      <div className="tag-list" style={{ marginBottom: 12, minHeight: 32 }}>
        {items.length === 0
          ? <span className="muted" style={{ fontSize: 12 }}>Nessun elemento</span>
          : items.map((item) => (
              <span key={item.value} className="tag">
                {item.label ? `${item.label} (${item.value})` : item.value}
                <button
                  onClick={() => onRemove(listKey, item.value)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', lineHeight: 1, padding: 0, fontWeight: 700, fontSize: 14 }}
                >×</button>
              </span>
            ))
        }
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          className="config-input"
          placeholder="Aggiungi…"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
          style={{ flex: 1, fontSize: 12 }}
        />
        <button className="btn btn-primary btn-sm" onClick={handleAdd} disabled={!newVal.trim()}>
          + Aggiungi
        </button>
      </div>
    </div>
  );
}

function ListeTab() {
  const queryClient = useQueryClient();

  const { data: lists = {}, isLoading: loadingL } = useQuery({
    queryKey: ['config-lists'],
    queryFn: fetchConfigLists,
    staleTime: 30_000,
  });

  const { data: blacklist = [], isLoading: loadingBL } = useQuery({
    queryKey: ['blacklist'],
    queryFn: fetchBlacklist,
    staleTime: 30_000,
  });

  const addListMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value, null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const removeListMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const [newBL, setNewBL] = useState('');
  const addBLMutation = useMutation({
    mutationFn: (kw) => addBlacklistItem(kw),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['blacklist'] }); setNewBL(''); },
  });
  const removeBLMutation = useMutation({
    mutationFn: (kw) => removeBlacklistItem(kw),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blacklist'] }),
  });

  // Liste gestite nelle pagine specifiche — non mostrate qui
  const CONTEXT_LISTS = new Set([
    'subreddits',        // → Reddit tab (News page)
    'channels_it',       // → YouTube Competitor tab
    'channels_en',       // → YouTube Competitor tab
    'yt_queries_it',     // → YouTube Competitor tab
    'yt_queries_en',     // → YouTube Competitor tab
    'tiktok_hashtags',   // → Social Discovery tab
    'instagram_hashtags',// → Social Discovery tab
    'rss_italian',       // → Trends RSS tab
    'rss_english',       // → Trends RSS tab
    'rss_podcasts',      // → Trends RSS tab
    'rss_tiktok',        // → Social
    'rss_instagram',     // → Social
    'rss_pinterest',     // → Pinterest
    'google_alerts',     // → Trends Google tab
  ]);

  // Filtra solo le liste globali (keywords, filter_words, ecc.)
  const globalEntries = Object.entries(lists).filter(([key]) => !CONTEXT_LISTS.has(key));

  if (loadingL || loadingBL) return <p className="muted">Caricamento…</p>;

  const blacklistItems = blacklist.map((kw) => ({ value: kw }));

  const allCards = [
    ...globalEntries.map(([key, items]) => ({ key, title: key.replace(/_/g, ' '), items })),
    { key: '__blacklist__', title: '🚫 Blacklist keyword', items: blacklistItems },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {allCards.map(({ key, title, items }) =>
        key === '__blacklist__' ? (
          <div className="card" key="__blacklist__">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-dim)', letterSpacing: '.8px' }}>
                🚫 Blacklist keyword
              </div>
            </div>
            <div className="tag-list" style={{ marginBottom: 12, minHeight: 32 }}>
              {blacklistItems.length === 0
                ? <span className="muted" style={{ fontSize: 12 }}>Nessuna keyword bloccata</span>
                : blacklistItems.map((item) => (
                    <span key={item.value} className="tag">
                      {item.value}
                      <button
                        onClick={() => removeBLMutation.mutate(item.value)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', lineHeight: 1, padding: 0, fontWeight: 700, fontSize: 14 }}
                      >×</button>
                    </span>
                  ))
              }
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="config-input"
                placeholder="Keyword da bloccare…"
                value={newBL}
                onChange={(e) => setNewBL(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && newBL.trim()) addBLMutation.mutate(newBL.trim()); }}
                style={{ flex: 1, fontSize: 12 }}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={() => addBLMutation.mutate(newBL.trim())}
                disabled={!newBL.trim() || addBLMutation.isPending}
              >+ Aggiungi</button>
            </div>
          </div>
        ) : (
          <ListCard
            key={key}
            listKey={key}
            title={title}
            items={items}
            onAdd={(lk, v) => addListMutation.mutate({ listKey: lk, value: v })}
            onRemove={(lk, v) => removeListMutation.mutate({ listKey: lk, value: v })}
          />
        )
      )}
    </div>
  );
}

// ── Logs ─────────────────────────────────────────────────────────────────────
const LEVEL_COLORS = {
  ERROR:   'var(--danger, #e53e3e)',
  WARNING: 'var(--warning, #d97706)',
  INFO:    'var(--text-dim, #888)',
};

const TIME_OPTIONS = [
  { label: 'Ultimi 30 min', value: 30 },
  { label: 'Ultima ora',    value: 60 },
  { label: 'Ultime 6h',    value: 360 },
  { label: 'Ultime 24h',   value: 1440 },
  { label: 'Ultime 48h',   value: 2880 },
];

function LogsTab() {
  const [minutes, setMinutes] = useState(60);
  const [level,   setLevel]   = useState('ALL');
  const tableRef = useRef(null);

  const { data: logs = [], isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['bot-logs', minutes, level],
    queryFn:  () => fetchLogs(minutes, level, 300),
    staleTime: 0,
    refetchInterval: 30_000,
  });

  // Scroll to top when new data arrives
  useEffect(() => {
    if (tableRef.current) tableRef.current.scrollTop = 0;
  }, [dataUpdatedAt]);

  function fmtTime(ts) {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return ts; }
  }

  const counts = logs.reduce((acc, l) => {
    acc[l.level] = (acc[l.level] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Filtri */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
          style={{
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6,
            color: 'var(--text)', padding: '5px 10px', fontSize: 12,
          }}
        >
          {TIME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {['ALL', 'ERROR', 'WARNING', 'INFO'].map((lv) => (
          <button
            key={lv}
            onClick={() => setLevel(lv)}
            style={{
              padding: '4px 12px', borderRadius: 6, border: '1px solid var(--border)',
              background: level === lv ? 'var(--accent)' : 'var(--surface)',
              color: level === lv ? '#fff' : (LEVEL_COLORS[lv] ?? 'var(--text)'),
              fontSize: 12, cursor: 'pointer', fontWeight: level === lv ? 700 : 400,
            }}
          >
            {lv}
            {lv !== 'ALL' && counts[lv] ? ` (${counts[lv]})` : ''}
          </button>
        ))}

        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)' }}>
          {logs.length} righe · aggiorna ogni 30s
        </span>
      </div>

      {/* Tabella */}
      <div
        ref={tableRef}
        className="card"
        style={{ overflowY: 'auto', maxHeight: '60vh', padding: 0 }}
      >
        {isLoading ? (
          <p className="muted" style={{ padding: 16 }}>Caricamento…</p>
        ) : logs.length === 0 ? (
          <EmptyState icon="📋" message="Nessun log trovato per il periodo selezionato." />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)', position: 'sticky', top: 0 }}>
                <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)', fontWeight: 600, whiteSpace: 'nowrap' }}>Ora</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)', fontWeight: 600 }}>Livello</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)', fontWeight: 600 }}>Modulo</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)', fontWeight: 600 }}>Messaggio</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: log.level === 'ERROR' ? 'rgba(229,62,62,0.06)'
                              : log.level === 'WARNING' ? 'rgba(217,119,6,0.05)'
                              : 'transparent',
                  }}
                >
                  <td style={{ padding: '6px 12px', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                    {fmtTime(log.logged_at)}
                  </td>
                  <td style={{ padding: '6px 12px', whiteSpace: 'nowrap' }}>
                    <span style={{
                      fontSize: 11, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                      color: LEVEL_COLORS[log.level] ?? 'var(--text-dim)',
                      background: log.level === 'ERROR' ? 'rgba(229,62,62,0.15)'
                                : log.level === 'WARNING' ? 'rgba(217,119,6,0.15)'
                                : 'var(--surface-alt, #1e1e1e)',
                    }}>
                      {log.level}
                    </span>
                  </td>
                  <td style={{ padding: '6px 12px', color: 'var(--text-dim)', whiteSpace: 'nowrap', fontSize: 11 }}>
                    {log.module}
                  </td>
                  <td style={{ padding: '6px 12px', color: 'var(--text)', fontFamily: 'monospace', fontSize: 11 }}>
                    {log.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Backup & API Keys ────────────────────────────────────────────────────────
const CRED_LABELS = {
  youtube:   'YouTube API',
  twitter:   'Twitter Bearer Token',
  reddit:    'Reddit API',
  apify:     'Apify API Key',
  news:      'NewsAPI',
  pinterest: 'Pinterest API',
  anthropic: 'Anthropic API Key',
};

function BackupTab() {
  const [downloading, setDownloading] = useState(false);
  const [restoring,   setRestoring]   = useState(false);
  const [restoreMsg,  setRestoreMsg]  = useState(null); // { ok, text }

  const { data: status } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 60_000,
    retry: false,
  });

  const totalRows = status
    ? Object.values(status.tables ?? {}).reduce((a, b) => a + b, 0)
    : null;

  async function handleDownload() {
    setDownloading(true);
    try {
      const blob = await downloadBackup();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `ytsperbot_backup_${new Date().toISOString().slice(0,16).replace('T','_').replace(':','')}.sql`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Errore download backup: ' + (e?.message ?? e));
    } finally {
      setDownloading(false);
    }
  }

  function handleRestorePick() {
    const input = document.createElement('input');
    input.type   = 'file';
    input.accept = '.sql';
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (!window.confirm(`Ripristinare il DB da "${file.name}"?\n\nI dati esistenti verranno sovrascritti dove in conflitto.`)) return;
      setRestoring(true);
      setRestoreMsg(null);
      try {
        const res = await restoreBackup(file);
        setRestoreMsg({
          ok:   true,
          text: `✅ Restore completato — ${res.inserted} righe inserite, ${res.skipped} saltate${res.errors?.length ? `, ${res.errors.length} errori` : ''}.`,
        });
      } catch (err) {
        const detail = err?.response?.data?.detail ?? err?.message ?? 'Errore sconosciuto';
        setRestoreMsg({ ok: false, text: `❌ ${detail}` });
      } finally {
        setRestoring(false);
      }
    };
    input.click();
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {/* DB stats */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">💾 Database</h2>
        </div>
        {!status ? (
          <p className="muted">Caricamento…</p>
        ) : (
          <>
            {[
              { label: 'Dimensione DB',      value: `${status.db_size_mb} MB` },
              { label: 'Righe totali',        value: totalRows?.toLocaleString('it-IT') ?? '—' },
              ...Object.entries(status.tables ?? {}).map(([t, n]) => ({
                label: t.replace(/_/g, ' '), value: n.toLocaleString('it-IT'),
              })),
            ].map(({ label, value }) => (
              <div key={label} className="config-row">
                <div style={{ flex: 1, fontSize: 13, color: 'var(--text-muted)' }}>{label}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{value}</div>
              </div>
            ))}

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button
                className="btn btn-primary"
                onClick={handleDownload}
                disabled={downloading}
                title="Scarica un dump SQL del DB"
              >
                {downloading ? '⏳ Download…' : '⬇️ Download backup'}
              </button>
              <button
                className="btn btn-ghost"
                onClick={handleRestorePick}
                disabled={restoring}
                title="Carica un file .sql per ripristinare il DB"
              >
                {restoring ? '⏳ Ripristino…' : '📂 Ripristina DB'}
              </button>
            </div>

            {restoreMsg && (
              <p style={{
                fontSize: 12, marginTop: 10,
                color: restoreMsg.ok ? 'var(--green)' : 'var(--accent)',
              }}>
                {restoreMsg.text}
              </p>
            )}

            <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8 }}>
              Il backup genera un dump SQL identico a <code>/backup</code> su Telegram.
              Il ripristino accetta file <code>.sql</code> prodotti dallo stesso comando.
            </p>
          </>
        )}
      </div>

      {/* API Keys */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">🔑 API Keys</h2>
        </div>
        {!status ? (
          <p className="muted">Caricamento…</p>
        ) : (
          Object.entries(status.credentials ?? {}).map(([key, ok]) => (
            <div key={key} className="config-row">
              <div style={{ flex: 1, fontSize: 13, color: 'var(--text-muted)' }}>
                {CRED_LABELS[key] ?? key}
              </div>
              <Badge variant={ok ? 'low' : 'high'}>
                {ok ? '✓ OK' : '✗ Mancante'}
              </Badge>
            </div>
          ))
        )}
      </div>

      {/* Attività bot 24h */}
      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <div className="card-header">
          <h2 className="card-title">🤖 Attività bot — ultime 24h</h2>
        </div>
        {!status ? (
          <p className="muted">Caricamento…</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            {[
              {
                icon: '👽', label: 'Post Reddit analizzati',
                value: status.activity?.reddit_posts_seen_24h ?? 0,
                sub: 'nelle ultime 24h',
              },
              {
                icon: '▶️', label: 'Video YouTube analizzati',
                value: status.activity?.yt_videos_seen_24h ?? 0,
                sub: 'nelle ultime 24h',
              },
              {
                icon: '🔔', label: 'Alert inviati',
                value: status.activity?.alerts_sent_24h ?? 0,
                sub: 'nelle ultime 24h',
              },
              {
                icon: '🔇', label: 'Alert deduplicati',
                value: status.activity?.alerts_dedup_24h ?? 0,
                sub: 'soppressi per dedup',
                tooltip: 'Il sistema sopprime alert duplicati per evitare spam su Telegram. Questo contatore mostra quanti (alert_type, keyword) unici hanno già ricevuto una notifica.',
              },
            ].map(({ icon, label, value, sub }) => (
              <div key={label} style={{
                background: 'var(--surface-alt, #1a1a1a)',
                borderRadius: 8, padding: '12px 14px',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ fontSize: 20 }}>{icon}</div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '.5px' }}>{label}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)' }}>{value.toLocaleString('it-IT')}</div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{sub}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function ConfigPage() {
  const [tab, setTab] = useState('params');
  const queryClient = useQueryClient();

  const { data: params = [], isLoading: loadingP } = useQuery({
    queryKey: ['config-params'],
    queryFn: fetchConfigParams,
    staleTime: 30_000,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }) => updateConfigParam(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-params'] }),
  });

  const visibleParams = params.filter(
    (p) => !HIDDEN_PARAMS.has(p.key) && !p.key.endsWith('_interval_hours') && !p.key.endsWith('_interval_minutes'),
  );

  const paramsBySection = visibleParams.reduce((acc, p) => {
    const section = p.key.split('.')[0] ?? 'altro';
    if (!acc[section]) acc[section] = [];
    acc[section].push(p);
    return acc;
  }, {});

  const TABS = [
    { key: 'params',   label: '⚙️ Parametri' },
    { key: 'schedule', label: '🕐 Schedule' },
    { key: 'lists',    label: '📋 Liste' },
    { key: 'backup',   label: '💾 Backup & API Keys' },
    { key: 'logs',     label: '📋 Logs' },
  ];

  return (
    <>
      <Topbar title="Config & Sistema" />
      <main className="page-content">
        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Parametri ───── */}
        {tab === 'params' && (
          <section className="card">
            {loadingP ? (
              <p className="muted">Caricamento…</p>
            ) : visibleParams.length === 0 ? (
              <EmptyState message="Nessun parametro trovato." />
            ) : (
              Object.entries(paramsBySection).map(([section, sectionParams]) => (
                <div key={section} style={{ marginBottom: 24 }}>
                  <div style={{
                    fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase',
                    color: 'var(--accent)', marginBottom: 12, letterSpacing: '0.06em',
                  }}>
                    {section}
                  </div>
                  {sectionParams.map((p) => (
                    <ParamRow
                      key={p.key}
                      param={p}
                      onSave={(key, value) => updateMutation.mutate({ key, value })}
                    />
                  ))}
                </div>
              ))
            )}
          </section>
        )}

        {/* ── Schedule ─────── */}
        {tab === 'schedule' && <ScheduleTab />}

        {/* ── Liste ──────────  */}
        {tab === 'lists' && <ListeTab />}

        {/* ── Backup ─────────  */}
        {tab === 'backup' && <BackupTab />}

        {/* ── Logs ───────────  */}
        {tab === 'logs' && <LogsTab />}
      </main>
    </>
  );
}
