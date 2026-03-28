/**
 * StatCard — top-level KPI card.
 * Props: label, value, sub (optional secondary line), accent (optional left-border color)
 */
export default function StatCard({ label, value, sub, accent }) {
  return (
    <div className="stat-card" style={accent ? { borderLeftColor: accent } : undefined}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
