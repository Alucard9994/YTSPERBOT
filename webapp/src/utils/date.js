/**
 * Parse a date string that may come from SQLite in format:
 *   '2026-03-27 03:43:23.225770+00:00'  (space separator — non-standard)
 * or standard ISO 8601:
 *   '2026-03-27T03:43:23.225770+00:00'
 *
 * Safari / Firefox reject the space-separated variant, so we normalize first.
 */
export function parseDate(s) {
  if (!s) return null;
  // Replace ONLY the first space (between date and time part) with 'T'
  const iso = String(s).replace(/^(\d{4}-\d{2}-\d{2}) /, '$1T');
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format a SQLite/ISO date string for display in it-IT locale.
 * Returns '—' for null / invalid values.
 */
export function fmtDate(s) {
  const d = parseDate(s);
  if (!d) return '—';
  return d.toLocaleString('it-IT');
}
