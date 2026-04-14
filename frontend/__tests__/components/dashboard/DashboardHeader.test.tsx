/**
 * Unit Tests: DashboardHeader Component
 *
 * Tests rendering, conditional controls, refresh button, and children.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import DashboardHeader from '@/components/dashboard/DashboardHeader';

// ── Test Suite ────────────────────────────────────────────────────────

describe('DashboardHeader Component', () => {
  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the title', () => {
      render(<DashboardHeader title="Dashboard Overview" />);
      expect(screen.getByText('Dashboard Overview')).toBeInTheDocument();
    });

    it('renders the subtitle when provided', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          subtitle="Last updated 5 minutes ago"
        />
      );
      expect(screen.getByText('Last updated 5 minutes ago')).toBeInTheDocument();
    });

    it('does not render subtitle when not provided', () => {
      render(<DashboardHeader title="Dashboard" />);
      // h1 should exist but no subtitle paragraph
      const h1 = screen.getByText('Dashboard');
      expect(h1.tagName).toBe('H1');
      expect(h1.parentElement!.querySelector('p')).toBeNull();
    });

    it('renders children when provided', () => {
      render(
        <DashboardHeader title="Dashboard">
          <button>Custom Action</button>
        </DashboardHeader>
      );
      expect(screen.getByText('Custom Action')).toBeInTheDocument();
    });

    it('does not render anything extra when only title provided', () => {
      const { container } = render(<DashboardHeader title="Minimal" />);
      expect(container.querySelector('h1')).toBeInTheDocument();
      // No date range selector, no refresh button, no children
      expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
      expect(screen.queryByTitle('Refresh data')).not.toBeInTheDocument();
    });
  });

  // ── DateRangeSelector ──────────────────────────────────────────────

  describe('DateRangeSelector', () => {
    it('shows DateRangeSelector when onDateChange is provided', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          onDateChange={jest.fn()}
        />
      );
      expect(screen.getByRole('tablist')).toBeInTheDocument();
    });

    it('hides DateRangeSelector when onDateChange is not provided', () => {
      render(<DashboardHeader title="Dashboard" />);
      expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    });

    it('passes datePreset and onDateChange to DateRangeSelector', () => {
      const mockDateChange = jest.fn();
      render(
        <DashboardHeader
          title="Dashboard"
          datePreset="7d"
          onDateChange={mockDateChange}
        />
      );
      // The "Last 7 Days" button should be clickable
      const preset7d = screen.getByText('Last 7 Days');
      expect(preset7d).toBeInTheDocument();
      fireEvent.click(preset7d);
      expect(mockDateChange).toHaveBeenCalled();
    });

    it('defaults datePreset to 30d', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          onDateChange={jest.fn()}
        />
      );
      // "Last 30 Days" should be active by default (orange styling)
      const preset30d = screen.getByText('Last 30 Days');
      expect(preset30d).toHaveClass('text-orange-400');
    });
  });

  // ── Refresh Button ─────────────────────────────────────────────────

  describe('Refresh Button', () => {
    it('shows refresh button when onRefresh is provided', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={jest.fn()}
        />
      );
      expect(screen.getByTitle('Refresh data')).toBeInTheDocument();
    });

    it('hides refresh button when onRefresh is not provided', () => {
      render(<DashboardHeader title="Dashboard" />);
      expect(screen.queryByTitle('Refresh data')).not.toBeInTheDocument();
    });

    it('calls onRefresh when refresh button is clicked', () => {
      const mockRefresh = jest.fn();
      render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={mockRefresh}
        />
      );
      const refreshBtn = screen.getByTitle('Refresh data');
      fireEvent.click(refreshBtn);
      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });

    it('disables refresh button when isRefreshing is true', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={jest.fn()}
          isRefreshing={true}
        />
      );
      const refreshBtn = screen.getByTitle('Refresh data');
      expect(refreshBtn).toBeDisabled();
    });

    it('enables refresh button when isRefreshing is false', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={jest.fn()}
          isRefreshing={false}
        />
      );
      const refreshBtn = screen.getByTitle('Refresh data');
      expect(refreshBtn).not.toBeDisabled();
    });

    it('applies spin animation to refresh icon when refreshing', () => {
      const { container } = render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={jest.fn()}
          isRefreshing={true}
        />
      );
      const svg = container.querySelector('.animate-spin');
      expect(svg).toBeInTheDocument();
    });

    it('does not spin refresh icon when not refreshing', () => {
      const { container } = render(
        <DashboardHeader
          title="Dashboard"
          onRefresh={jest.fn()}
          isRefreshing={false}
        />
      );
      const svg = container.querySelector('.animate-spin');
      expect(svg).toBeNull();
    });
  });

  // ── Layout ─────────────────────────────────────────────────────────

  describe('Layout', () => {
    it('has border-b styling at the bottom', () => {
      const { container } = render(<DashboardHeader title="Dashboard" />);
      const header = container.firstChild as HTMLElement;
      expect(header.className).toContain('border-b');
    });

    it('renders title as h1 element', () => {
      render(<DashboardHeader title="My Title" />);
      const h1 = screen.getByText('My Title');
      expect(h1.tagName).toBe('H1');
    });

    it('title has white text and bold styling', () => {
      render(<DashboardHeader title="Styled Title" />);
      const h1 = screen.getByText('Styled Title');
      expect(h1.className).toContain('text-white');
      expect(h1.className).toContain('font-bold');
    });

    it('subtitle has zinc-500 text color', () => {
      render(
        <DashboardHeader
          title="Dashboard"
          subtitle="A subtitle"
        />
      );
      const subtitle = screen.getByText('A subtitle');
      expect(subtitle.className).toContain('text-zinc-500');
    });

    it('renders DateRangeSelector, refresh button, and children together', () => {
      render(
        <DashboardHeader
          title="Full"
          subtitle="All features"
          onDateChange={jest.fn()}
          onRefresh={jest.fn()}
        >
          <span>Extra Child</span>
        </DashboardHeader>
      );
      expect(screen.getByRole('tablist')).toBeInTheDocument();
      expect(screen.getByTitle('Refresh data')).toBeInTheDocument();
      expect(screen.getByText('Extra Child')).toBeInTheDocument();
    });
  });
});
