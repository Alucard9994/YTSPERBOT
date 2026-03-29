import { useState, useEffect } from 'react';
import { bootstrapToken, getToken, setToken, clearToken } from '../auth.js';
import axios from 'axios';

/**
 * AuthGate — blocca il render dell'app finché non è presente un token valido.
 *
 * Flusso:
 *  1. bootstrapToken() legge ?token= dall'URL (o da localStorage)
 *  2. Se trovato, lo verifica con una chiamata a /api/dashboard/keywords?limit=1
 *  3. Se 401 → mostra schermata di inserimento token manuale
 *  4. Se ok → renderizza {children}
 */
export default function AuthGate({ children }) {
  const [status, setStatus] = useState('checking'); // 'checking' | 'ok' | 'denied'
  const [inputVal, setInputVal] = useState('');
  const [error, setError] = useState('');

  async function checkToken(token) {
    if (!token) { setStatus('denied'); return; }
    try {
      await axios.get('/api/dashboard/keywords', {
        params: { hours: 1, limit: 1 },
        headers: { 'X-Dashboard-Token': token },
        timeout: 10_000,
      });
      setToken(token);
      setStatus('ok');
    } catch (e) {
      if (e.response?.status === 401) {
        clearToken();
        setStatus('denied');
        setError('Token non valido. Controlla il link ricevuto su Telegram.');
      } else {
        // Errore di rete o server — lasciamo passare (token probabilmente ok, backend momentaneamente down)
        setToken(token);
        setStatus('ok');
      }
    }
  }

  useEffect(() => {
    const token = bootstrapToken();
    checkToken(token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === 'checking') {
    return (
      <div style={styles.overlay}>
        <div style={styles.spinner}>⏳ Verifica accesso…</div>
      </div>
    );
  }

  if (status === 'ok') return children;

  // status === 'denied'
  return (
    <div style={styles.overlay}>
      <div style={styles.box}>
        <div style={styles.icon}>🔒</div>
        <h1 style={styles.title}>Accesso protetto</h1>
        <p style={styles.sub}>
          Usa il link inviato dal bot Telegram, oppure incolla qui il tuo token.
        </p>
        {error && <p style={styles.errorMsg}>{error}</p>}
        <input
          style={styles.input}
          type="text"
          placeholder="Incolla il token qui…"
          value={inputVal}
          onChange={(e) => { setInputVal(e.target.value); setError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && inputVal.trim()) checkToken(inputVal.trim()); }}
          autoFocus
        />
        <button
          style={styles.btn}
          disabled={!inputVal.trim()}
          onClick={() => checkToken(inputVal.trim())}
        >
          Accedi
        </button>
      </div>
    </div>
  );
}

// ── Inline styles (no CSS file needed) ────────────────────────────────────────

const styles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'var(--bg, #0d0d0d)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 9999,
  },
  spinner: {
    color: 'var(--text-dim, #888)',
    fontSize: 16,
  },
  box: {
    background: 'var(--surface, #1a1a1a)',
    border: '1px solid var(--border, #2a2a2a)',
    borderRadius: 12,
    padding: '40px 36px',
    maxWidth: 400,
    width: '90%',
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  icon: { fontSize: 40 },
  title: { margin: 0, fontSize: 22, color: 'var(--text, #fff)', fontWeight: 700 },
  sub: { margin: 0, fontSize: 14, color: 'var(--text-dim, #888)', lineHeight: 1.5 },
  errorMsg: { margin: 0, fontSize: 13, color: '#e94560', background: 'rgba(233,69,96,.1)', borderRadius: 6, padding: '8px 12px' },
  input: {
    width: '100%',
    padding: '10px 14px',
    background: 'var(--bg, #0d0d0d)',
    border: '1px solid var(--border, #2a2a2a)',
    borderRadius: 8,
    color: 'var(--text, #fff)',
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
  },
  btn: {
    padding: '10px 24px',
    background: 'var(--accent, #4f8ef7)',
    border: 'none',
    borderRadius: 8,
    color: '#fff',
    fontWeight: 700,
    fontSize: 15,
    cursor: 'pointer',
    opacity: 1,
  },
};
