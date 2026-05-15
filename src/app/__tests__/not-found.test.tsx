/**
 * PARWA Day 5 Unit Tests — 404 Not Found Page
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('next/link', () => {
  return function MockLink(props: Record<string, unknown>) {
    return React.createElement('a', { href: props.href as string }, props.children);
  };
});

jest.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(_target: Record<string, unknown>, prop: string) {
      return (props: Record<string, unknown>) =>
        React.createElement('svg', { 'data-testid': `icon-${prop.toLowerCase()}`, ...props });
    },
  });
});

const NotFoundPage = require('@/app/not-found').default;

describe('NotFoundPage', () => {
  it('renders the 404 heading', () => {
    render(React.createElement(NotFoundPage));
    expect(screen.getByText('404')).toBeInTheDocument();
  });

  it('renders "Page not found" message', () => {
    render(React.createElement(NotFoundPage));
    expect(screen.getByText('Page not found')).toBeInTheDocument();
  });

  it('has a link to the dashboard', () => {
    render(React.createElement(NotFoundPage));
    const dashboardLink = screen.getByText('Go to Dashboard');
    expect(dashboardLink).toBeInTheDocument();
    expect(dashboardLink.closest('a')).toHaveAttribute('href', '/dashboard');
  });

  it('has a Go Back button', () => {
    render(React.createElement(NotFoundPage));
    expect(screen.getByText('Go Back')).toBeInTheDocument();
  });
});
