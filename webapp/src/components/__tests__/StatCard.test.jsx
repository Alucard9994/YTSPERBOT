import { render, screen } from '@testing-library/react';
import StatCard from '../StatCard.jsx';

describe('StatCard', () => {
  it('renders value and label', () => {
    render(<StatCard value="42" label="Alert (48h)" />);
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Alert (48h)')).toBeInTheDocument();
  });

  it('renders sub text when provided', () => {
    render(<StatCard value="5" label="Test" sub="ultimi 7 giorni" />);
    expect(screen.getByText('ultimi 7 giorni')).toBeInTheDocument();
  });

  it('does not render sub element when not provided', () => {
    const { container } = render(<StatCard value="0" label="Test" />);
    expect(container.querySelector('.stat-sub')).not.toBeInTheDocument();
  });

  it('applies custom accent color via inline style', () => {
    const { container } = render(<StatCard value="1" label="L" accent="#ff0000" />);
    expect(container.firstChild).toHaveStyle({ borderLeftColor: '#ff0000' });
  });

  it('no inline style when accent not provided', () => {
    const { container } = render(<StatCard value="1" label="L" />);
    // Nessun borderLeftColor inline (usa quello del CSS)
    expect(container.firstChild.getAttribute('style')).toBeFalsy();
  });
});
