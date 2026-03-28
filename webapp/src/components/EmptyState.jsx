/**
 * EmptyState — shown when a section has no data yet.
 */
export default function EmptyState({ icon = '📭', message = 'Nessun dato disponibile.' }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <p>{message}</p>
    </div>
  );
}
