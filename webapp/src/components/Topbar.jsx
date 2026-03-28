import { useQuery } from '@tanstack/react-query';
import { fetchSystemStatus } from '../api/client.js';

export default function Topbar({ title }) {
  const { data } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const allOk =
    data &&
    Object.values(data.credentials ?? {}).every(Boolean);

  return (
    <header className="topbar">
      <h1 className="topbar-title">{title}</h1>
      <div className="topbar-right">
        {data && (
          <span
            className={`status-dot ${allOk ? 'ok' : 'warn'}`}
            title={allOk ? 'Tutte le credenziali OK' : 'Alcune credenziali mancanti — vedi Configurazione'}
          />
        )}
        <span className="topbar-db">
          {data ? `DB ${data.db_size_mb} MB` : '…'}
        </span>
      </div>
    </header>
  );
}
