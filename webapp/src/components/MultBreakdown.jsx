/**
 * MultBreakdown
 * Shows two multiplier rows: vs average views (green) and vs subscribers (blue).
 * Props: multAvg, multSubs — raw numbers (e.g. 4.2) or pre-formatted strings (e.g. "4.2x")
 */
export default function MultBreakdown({ multAvg, multSubs }) {
  function fmt(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return `${v.toFixed(1)}x`;
    return String(v).endsWith('x') ? v : `${v}x`;
  }

  return (
    <div className="mult-box">
      <div className="mult-row">
        <span className="mult-label">vs views medie</span>
        <span className="mult-val" style={{ color: '#22c55e' }}>{fmt(multAvg)}</span>
      </div>
      <div className="mult-row">
        <span className="mult-label">vs iscritti</span>
        <span className="mult-val" style={{ color: '#60a5fa' }}>{fmt(multSubs)}</span>
      </div>
    </div>
  );
}
