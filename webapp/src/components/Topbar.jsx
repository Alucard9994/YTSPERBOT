import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSystemStatus, triggerRunServices, triggerRestart } from '../api/client.js';

const SERVICES = [
  { id: 'rss',               label: '📡 RSS Detector' },
  { id: 'reddit',            label: '👽 Reddit' },
  { id: 'twitter',           label: '🐦 Twitter / X' },
  { id: 'trends',            label: '📈 Google Trends' },
  { id: 'comments',          label: '💬 YouTube Comments' },
  { id: 'scraper',           label: '▶️ YouTube Scraper' },
  { id: 'new_video',         label: '🆕 Competitor Nuovi Video' },
  { id: 'subscriber_growth', label: '📊 Crescita Iscritti' },
  { id: 'pinterest',         label: '📌 Pinterest' },
  { id: 'cross_signal',      label: '🔗 Cross Signal' },
  { id: 'news',              label: '📰 News Detector' },
  { id: 'social',            label: '🎵 TikTok + Instagram (Apify)' },
];

function RunServiziModal({ onClose }) {
  const [selected, setSelected] = useState(new Set(SERVICES.map((s) => s.id)));
  const [running, setRunning]   = useState(false);
  const [done, setDone]         = useState(false);

  function toggle(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function selectAll()  { setSelected(new Set(SERVICES.map((s) => s.id))); }
  function selectNone() { setSelected(new Set()); }

  async function handleRun() {
    if (running || selected.size === 0) return;
    setRunning(true);
    try {
      await triggerRunServices([...selected]);
      setDone(true);
      setTimeout(onClose, 1800);
    } catch (_) {
      setRunning(false);
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--surface)',
        borderRadius: 12,
        padding: '24px 28px',
        width: 380,
        boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text)' }}>▶️ Run Servizi</h3>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--text-dim)', lineHeight: 1 }}
          >×</button>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-ghost" onClick={selectAll}>Tutti</button>
          <button className="btn btn-sm btn-ghost" onClick={selectNone}>Nessuno</button>
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-dim)', alignSelf: 'center' }}>
            {selected.size}/{SERVICES.length} selezionati
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {SERVICES.map((svc) => (
            <label
              key={svc.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '6px 8px', borderRadius: 6, cursor: 'pointer',
                background: selected.has(svc.id) ? 'var(--surface-alt, #1e1e1e)' : 'transparent',
                transition: 'background 0.15s',
              }}
            >
              <input
                type="checkbox"
                checked={selected.has(svc.id)}
                onChange={() => toggle(svc.id)}
                style={{ accentColor: 'var(--accent)', width: 15, height: 15 }}
              />
              <span style={{ fontSize: 13, color: 'var(--text)' }}>{svc.label}</span>
            </label>
          ))}
        </div>

        <button
          className="btn btn-primary"
          onClick={handleRun}
          disabled={running || selected.size === 0}
          style={{ marginTop: 4 }}
        >
          {done ? '✅ Avviati!' : running ? '⏳ Avvio in corso…' : `▶️ Run (${selected.size})`}
        </button>
      </div>
    </div>
  );
}

function RestartModal({ onClose }) {
  const [status, setStatus] = useState('idle'); // idle | loading | done | error

  async function handleRestart() {
    setStatus('loading');
    try {
      await triggerRestart();
      setStatus('done');
    } catch (_) {
      setStatus('error');
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--surface)',
        borderRadius: 12,
        padding: '24px 28px',
        width: 360,
        boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text)' }}>🔁 Riavvia Servizio</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--text-dim)', lineHeight: 1 }}>×</button>
        </div>

        {status === 'idle' && (
          <>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.5 }}>
              Il servizio Render verrà riavviato. Il bot sarà offline per ~30 secondi.<br/><br/>
              <strong style={{ color: 'var(--text)' }}>⚠️ Il database in memoria verrà perso</strong> — usa Backup prima se necessario.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={onClose}>Annulla</button>
              <button className="btn btn-danger" onClick={handleRestart}>🔁 Riavvia</button>
            </div>
          </>
        )}
        {status === 'loading' && <p style={{ margin: 0, color: 'var(--text-dim)', fontSize: 13 }}>⏳ Riavvio in corso…</p>}
        {status === 'done'    && <p style={{ margin: 0, color: '#4ade80', fontSize: 13 }}>✅ Riavvio richiesto. Il bot tornerà online tra ~30s.</p>}
        {status === 'error'   && (
          <>
            <p style={{ margin: 0, color: '#f87171', fontSize: 13 }}>❌ Errore. Verifica che RENDER_API_KEY e RENDER_SERVICE_ID siano configurati.</p>
            <button className="btn btn-ghost" onClick={onClose}>Chiudi</button>
          </>
        )}
      </div>
    </div>
  );
}

export default function Topbar({ title, subtitle }) {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [showRestart, setShowRestart] = useState(false);

  const { data } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const now = new Date().toLocaleTimeString('it-IT', {
    hour: '2-digit',
    minute: '2-digit',
  });

  async function handleRefresh() {
    await queryClient.invalidateQueries();
  }

  return (
    <>
      <header className="topbar">
        <div>
          <div className="topbar-title">{title}</div>
          <div className="topbar-subtitle">
            {subtitle ?? `Aggiornato ${now}`}
          </div>
        </div>

        <div className="topbar-actions">
          <button className="btn btn-ghost" onClick={handleRefresh} title="Invalida la cache e ricarica i dati">
            🔄 Refresh
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => setShowRestart(true)}
            title="Riavvia il servizio Render (~30s offline)"
            style={{ color: '#f87171' }}
          >
            🔁 Riavvia
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setShowModal(true)}
            title="Scegli quali servizi eseguire manualmente"
          >
            ▶️ Run Servizi
          </button>
        </div>
      </header>

      {showModal   && <RunServiziModal onClose={() => setShowModal(false)} />}
      {showRestart && <RestartModal   onClose={() => setShowRestart(false)} />}
    </>
  );
}
