import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSystemStatus, triggerRunAll } from '../api/client.js';

export default function Topbar({ title, subtitle }) {
  const queryClient = useQueryClient();
  const [running, setRunning] = useState(false);

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

  async function handleRunAll() {
    if (running) return;
    setRunning(true);
    try {
      await triggerRunAll();
    } catch (_) {
      // ignore — the bot might not expose the endpoint in all environments
    } finally {
      setTimeout(() => setRunning(false), 3000);
    }
  }

  return (
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
          className="btn btn-primary"
          onClick={handleRunAll}
          disabled={running}
          title="Avvia manualmente tutti i job del bot"
        >
          {running ? '⏳ Running…' : '▶️ Run all'}
        </button>
      </div>
    </header>
  );
}
