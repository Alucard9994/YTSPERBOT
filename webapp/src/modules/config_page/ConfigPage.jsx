import { useState } from 'react';
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
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';

function CredentialRow({ label, ok }) {
  return (
    <div className="config-row">
      <span className="config-label">{label}</span>
      <span style={{ color: ok ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
        {ok ? '✅ OK' : '❌ Mancante'}
      </span>
    </div>
  );
}

function ParamRow({ param, onSave }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(param.value ?? '');

  function handleSave() {
    onSave(param.key, val);
    setEditing(false);
  }

  return (
    <div className="config-row">
      <div style={{ flex: 1 }}>
        <div className="config-label">{param.label ?? param.key}</div>
        <div className="config-key muted">{param.key}</div>
      </div>
      {editing ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="config-input"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false); }}
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

function ListSection({ listKey, title, items, onAdd, onRemove }) {
  const [newVal, setNewVal] = useState('');
  const [newLabel, setNewLabel] = useState('');

  function handleAdd() {
    if (!newVal.trim()) return;
    onAdd(listKey, newVal.trim(), newLabel.trim() || null);
    setNewVal('');
    setNewLabel('');
  }

  const hasLabel = items.some((i) => i.label);

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 10, color: 'var(--text)' }}>
        {title} ({items.length})
      </h3>

      {items.length === 0 ? (
        <p className="muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>Nessun elemento.</p>
      ) : (
        <div className="tag-list" style={{ marginBottom: 10 }}>
          {items.map((item) => (
            <span key={item.value} className="tag" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {item.label ? `${item.label} (${item.value})` : item.value}
              <button
                onClick={() => onRemove(listKey, item.value)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', lineHeight: 1, padding: 0 }}
                title="Rimuovi"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input
          className="config-input"
          placeholder="Valore"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
          style={{ flex: '1 1 140px' }}
        />
        {hasLabel && (
          <input
            className="config-input"
            placeholder="Etichetta (opzionale)"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            style={{ flex: '1 1 140px' }}
          />
        )}
        <button className="btn btn-primary btn-sm" onClick={handleAdd} disabled={!newVal.trim()}>
          Aggiungi
        </button>
      </div>
    </div>
  );
}

export default function ConfigPage() {
  const [tab, setTab] = useState('params');
  const queryClient = useQueryClient();

  const { data: params = [], isLoading: loadingP } = useQuery({
    queryKey: ['config-params'],
    queryFn: fetchConfigParams,
    staleTime: 30_000,
  });

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

  const { data: status } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }) => updateConfigParam(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-params'] }),
  });

  const addListMutation = useMutation({
    mutationFn: ({ listKey, value, label }) => addConfigListItem(listKey, value, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const removeListMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  const [newBLItem, setNewBLItem] = useState('');
  const addBLMutation = useMutation({
    mutationFn: (kw) => addBlacklistItem(kw),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['blacklist'] }); setNewBLItem(''); },
  });
  const removeBLMutation = useMutation({
    mutationFn: (kw) => removeBlacklistItem(kw),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blacklist'] }),
  });

  // Group params by section prefix
  const paramsBySection = params.reduce((acc, p) => {
    const section = p.key.split('.')[0] ?? 'altro';
    if (!acc[section]) acc[section] = [];
    acc[section].push(p);
    return acc;
  }, {});

  return (
    <>
      <Topbar title="Configurazione" />
      <main className="page-content">
        <div className="tabs">
          {[
            { key: 'params', label: 'Parametri' },
            { key: 'lists', label: 'Liste' },
            { key: 'blacklist', label: `Blacklist (${blacklist.length})` },
            { key: 'status', label: 'Stato sistema' },
          ].map((t) => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Params ─────────────────────────────────── */}
        {tab === 'params' && (
          <section className="card">
            {loadingP ? (
              <p className="muted">Caricamento…</p>
            ) : params.length === 0 ? (
              <EmptyState message="Nessun parametro trovato." />
            ) : (
              Object.entries(paramsBySection).map(([section, sectionParams]) => (
                <div key={section} style={{ marginBottom: 24 }}>
                  <h3 style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 12, letterSpacing: '0.05em' }}>
                    {section}
                  </h3>
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

        {/* ── Lists ──────────────────────────────────── */}
        {tab === 'lists' && (
          <section className="card">
            {loadingL ? (
              <p className="muted">Caricamento…</p>
            ) : Object.keys(lists).length === 0 ? (
              <EmptyState message="Nessuna lista configurata." />
            ) : (
              Object.entries(lists).map(([listKey, items]) => (
                <ListSection
                  key={listKey}
                  listKey={listKey}
                  title={listKey.replace(/_/g, ' ')}
                  items={items}
                  onAdd={(lk, v, l) => addListMutation.mutate({ listKey: lk, value: v, label: l })}
                  onRemove={(lk, v) => removeListMutation.mutate({ listKey: lk, value: v })}
                />
              ))
            )}
          </section>
        )}

        {/* ── Blacklist ───────────────────────────────── */}
        {tab === 'blacklist' && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Keyword in blacklist</h2>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <input
                className="config-input"
                placeholder="Keyword da bloccare"
                value={newBLItem}
                onChange={(e) => setNewBLItem(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && newBLItem.trim()) addBLMutation.mutate(newBLItem.trim()); }}
                style={{ flex: 1 }}
              />
              <button
                className="btn btn-danger"
                disabled={!newBLItem.trim() || addBLMutation.isPending}
                onClick={() => addBLMutation.mutate(newBLItem.trim())}
              >
                Aggiungi
              </button>
            </div>

            {loadingBL ? (
              <p className="muted">Caricamento…</p>
            ) : blacklist.length === 0 ? (
              <EmptyState icon="🚫" message="Nessuna keyword in blacklist." />
            ) : (
              <div className="tag-list">
                {blacklist.map((item) => (
                  <span key={item.keyword} className="tag" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {item.keyword}
                    <button
                      onClick={() => removeBLMutation.mutate(item.keyword)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', lineHeight: 1, padding: 0, fontWeight: 700 }}
                      title="Rimuovi dalla blacklist"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── Status ─────────────────────────────────── */}
        {tab === 'status' && (
          <>
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Credenziali</h2>
              </div>
              {!status ? (
                <p className="muted">Caricamento…</p>
              ) : (
                Object.entries(status.credentials ?? {}).map(([k, ok]) => (
                  <CredentialRow key={k} label={k} ok={ok} />
                ))
              )}
            </section>

            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Database</h2>
              </div>
              {!status ? (
                <p className="muted">Caricamento…</p>
              ) : (
                <>
                  <div className="config-row">
                    <span className="config-label">Dimensione DB</span>
                    <span>{status.db_size_mb} MB</span>
                  </div>
                  {Object.entries(status.tables ?? {}).map(([table, count]) => (
                    <div key={table} className="config-row">
                      <span className="config-label config-key">{table}</span>
                      <span>{count} righe</span>
                    </div>
                  ))}
                </>
              )}
            </section>
          </>
        )}
      </main>
    </>
  );
}
