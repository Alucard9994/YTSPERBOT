import { render, screen } from '@testing-library/react';
import Badge from '../Badge.jsx';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>SHORT</Badge>);
    expect(screen.getByText('SHORT')).toBeInTheDocument();
  });

  it('applies default variant class when no variant given', () => {
    const { container } = render(<Badge>text</Badge>);
    expect(container.firstChild).toHaveClass('badge-default');
  });

  it('applies short variant class', () => {
    const { container } = render(<Badge variant="short">SHORT</Badge>);
    expect(container.firstChild).toHaveClass('badge-short');
  });

  it('applies long variant class', () => {
    const { container } = render(<Badge variant="long">LONG</Badge>);
    expect(container.firstChild).toHaveClass('badge-long');
  });

  it('applies high variant class', () => {
    const { container } = render(<Badge variant="high">ALTA</Badge>);
    expect(container.firstChild).toHaveClass('badge-high');
  });

  it('applies medium variant class', () => {
    const { container } = render(<Badge variant="medium">MEDIA</Badge>);
    expect(container.firstChild).toHaveClass('badge-medium');
  });

  it('always has base badge class', () => {
    const { container } = render(<Badge variant="low">LOW</Badge>);
    expect(container.firstChild).toHaveClass('badge');
  });
});
