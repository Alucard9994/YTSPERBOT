/**
 * Badge — small coloured pill.
 * variant: 'short' | 'long' | 'high' | 'medium' | 'low' | 'default'
 */
export default function Badge({ children, variant = 'default' }) {
  return <span className={`badge badge-${variant}`}>{children}</span>;
}
