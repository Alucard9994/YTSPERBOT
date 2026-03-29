import { useState } from 'react';

/**
 * Inline list manager — mostra gli elementi come lista verticale con link + pulsante ×.
 *
 * Props:
 *   listKey      – chiave della lista (es. 'subreddits')
 *   items        – array di { value, label? } o stringhe
 *   onAdd        – (listKey, value) => void
 *   onRemove     – (listKey, value) => void
 *   placeholder  – testo placeholder dell'input
 *   renderLabel  – (item) => string  — come visualizzare il testo dell'elemento
 *   getUrl       – (item) => string | null  — URL da aprire al click (link ↗)
 *   isPending    – disabilita i controlli durante una mutation in corso
 */
export default function InlineListManager({
  listKey,
  items = [],
  onAdd,
  onRemove,
  placeholder = 'Aggiungi…',
  renderLabel = null,
  getUrl = null,
  isPending = false,
}) {
  const [newVal, setNewVal] = useState('');

  function handleAdd() {
    const v = newVal.trim();
    if (!v) return;
    onAdd(listKey, v);
    setNewVal('');
  }

  return (
    <div>
      {/* ── Lista elementi ── */}
      {items.length === 0 ? (
        <p className="muted" style={{ fontSize: 12, margin: '0 0 10px' }}>
          Nessun elemento — aggiungine uno sotto
        </p>
      ) : (
        <div style={{ marginBottom: 10 }}>
          {items.map((item) => {
            const val   = item.value ?? item;
            const label = renderLabel ? renderLabel(item) : (item.label || val);
            const url   = getUrl ? getUrl(item) : null;

            return (
              <div
                key={val}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 2px',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {url ? (
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      flex: 1, fontSize: 13,
                      color: 'var(--text)', textDecoration: 'none',
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
                    onMouseLeave={e => e.currentTarget.style.color = 'var(--text)'}
                  >
                    {label}
                    <span style={{ marginLeft: 4, opacity: 0.4, fontSize: 11 }}>↗</span>
                  </a>
                ) : (
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text)' }}>
                    {label}
                  </span>
                )}

                <button
                  onClick={() => onRemove(listKey, val)}
                  disabled={isPending}
                  title="Rimuovi"
                  style={{
                    background: 'none',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                    color: 'var(--text-dim)',
                    width: 22, height: 22,
                    borderRadius: 4,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, lineHeight: 1, flexShrink: 0,
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.color = 'var(--accent)';
                    e.currentTarget.style.borderColor = 'var(--accent)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.color = 'var(--text-dim)';
                    e.currentTarget.style.borderColor = 'var(--border)';
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Form aggiunta ── */}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <input
          className="config-input"
          placeholder={placeholder}
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
          style={{ flex: 1, fontSize: 12 }}
          disabled={isPending}
        />
        <button
          className="btn btn-primary btn-sm"
          onClick={handleAdd}
          disabled={!newVal.trim() || isPending}
        >
          + Aggiungi
        </button>
      </div>
    </div>
  );
}
