import { useState } from 'react';

/**
 * Reusable inline list manager (add/remove items from a config_list).
 * Props:
 *   listKey     – the config list key (e.g. 'subreddits')
 *   items       – array of { value, label? } objects
 *   onAdd       – (listKey, value) => void
 *   onRemove    – (listKey, value) => void
 *   placeholder – input placeholder text
 *   renderTag   – optional (item) => ReactNode to customize tag label
 *   isPending   – disable while mutation is in flight
 */
export default function InlineListManager({
  listKey,
  items = [],
  onAdd,
  onRemove,
  placeholder = 'Aggiungi…',
  renderTag = null,
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
      <div className="tag-list" style={{ marginBottom: 10, minHeight: 28 }}>
        {items.length === 0 ? (
          <span className="muted" style={{ fontSize: 12 }}>Nessun elemento — aggiungi dal form sotto</span>
        ) : (
          items.map(item => {
            const val     = item.value ?? item;
            const display = renderTag ? renderTag(item) : (item.label || val);
            return (
              <span key={val} className="tag">
                {display}
                <button
                  onClick={() => onRemove(listKey, val)}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--danger)', lineHeight: 1,
                    padding: '0 0 0 5px', fontWeight: 700, fontSize: 14,
                  }}
                  title="Rimuovi"
                  disabled={isPending}
                >×</button>
              </span>
            );
          })
        )}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
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
