import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InfoTooltip from '../InfoTooltip.jsx';

describe('InfoTooltip', () => {
  it('renders the trigger element', () => {
    render(<InfoTooltip text="Spiegazione" />);
    expect(screen.getByText('i')).toBeInTheDocument();
  });

  it('renders the bubble text in the DOM (hidden via CSS)', () => {
    render(<InfoTooltip text="Questa è la spiegazione." />);
    // Il testo è nel DOM anche quando il tooltip non è visibile (visibility via CSS)
    expect(screen.getByText('Questa è la spiegazione.')).toBeInTheDocument();
  });

  it('trigger has tooltip-trigger class', () => {
    const { container } = render(<InfoTooltip text="x" />);
    expect(container.querySelector('.tooltip-trigger')).toBeInTheDocument();
  });

  it('bubble has tooltip-bubble class', () => {
    const { container } = render(<InfoTooltip text="x" />);
    expect(container.querySelector('.tooltip-bubble')).toBeInTheDocument();
  });

  it('wrapper has tooltip-wrap class', () => {
    const { container } = render(<InfoTooltip text="x" />);
    expect(container.querySelector('.tooltip-wrap')).toBeInTheDocument();
  });
});
