/**
 * Sparkline — mini grafico SVG a linea per serie temporali.
 * Nessuna dipendenza esterna, puro SVG inline.
 *
 * Props:
 *  - points: array di numeri (o oggetti con campo `subscribers`)
 *  - width, height: dimensioni SVG (default 80×28)
 *  - color: colore linea (default var(--accent))
 *  - dotColor: colore punto finale (default uguale a color)
 */
export default function Sparkline({
  points = [],
  width = 80,
  height = 28,
  color = 'var(--accent)',
  dotColor = null,
}) {
  // Normalizza: accetta array di numeri o array di oggetti {subscribers|value}
  const values = points.map((p) =>
    typeof p === 'number' ? p : (p.subscribers ?? p.value ?? 0)
  );

  if (values.length < 2) {
    return (
      <span style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '.5px' }}>
        —
      </span>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pad = 2; // padding verticale px

  // Calcola coordinate
  const coords = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = pad + (1 - (v - min) / range) * (height - pad * 2);
    return [x, y];
  });

  const polyline = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');

  // Punto finale (ultimo valore)
  const [lastX, lastY] = coords[coords.length - 1];
  const dot = dotColor ?? color;

  // Trend: positivo = verde, negativo = rosso
  const trend = values[values.length - 1] - values[0];
  const lineColor = color === 'auto'
    ? trend >= 0 ? '#22c55e' : '#e94560'
    : color;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: 'block', overflow: 'visible' }}
    >
      <polyline
        points={polyline}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Punto finale evidenziato */}
      <circle cx={lastX} cy={lastY} r="2.5" fill={dot === 'auto' ? lineColor : dot} />
    </svg>
  );
}
