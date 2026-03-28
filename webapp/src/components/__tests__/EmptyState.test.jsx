import { render, screen } from '@testing-library/react';
import EmptyState from '../EmptyState.jsx';

describe('EmptyState', () => {
  it('shows default message', () => {
    render(<EmptyState />);
    expect(screen.getByText('Nessun dato disponibile.')).toBeInTheDocument();
  });

  it('shows custom message', () => {
    render(<EmptyState message="Nessun alert nelle ultime 48 ore." />);
    expect(screen.getByText('Nessun alert nelle ultime 48 ore.')).toBeInTheDocument();
  });

  it('shows default icon', () => {
    render(<EmptyState />);
    expect(screen.getByText('📭')).toBeInTheDocument();
  });

  it('shows custom icon', () => {
    render(<EmptyState icon="🎬" message="Nessun video." />);
    expect(screen.getByText('🎬')).toBeInTheDocument();
  });
});
