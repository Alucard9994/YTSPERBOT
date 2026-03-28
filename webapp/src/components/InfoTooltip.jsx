/**
 * InfoTooltip — inline (i) bubble with hover popover.
 * Usage: <InfoTooltip text="Spiegazione..." />
 */
export default function InfoTooltip({ text }) {
  return (
    <span className="tooltip-wrap">
      <span className="tooltip-trigger">i</span>
      <span className="tooltip-bubble">{text}</span>
    </span>
  );
}
