/**
 * Unit Tests: KPICard Component
 *
 * Tests rendering, variants, trend display, loading skeleton, and edge cases.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import KPICard from '@/components/dashboard/KPICard';

// ── Test Suite ────────────────────────────────────────────────────────

describe('KPICard Component', () => {
  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the title', () => {
      render(
        <KPICard
          title="Total Tickets"
          value={1234}
          icon={<span data-testid="icon">🎫</span>}
        />
      );
      expect(screen.getByText('Total Tickets')).toBeInTheDocument();
    });

    it('renders the value as string', () => {
      render(
        <KPICard
          title="Revenue"
          value="$42,000"
          icon={<span data-testid="icon">💰</span>}
        />
      );
      expect(screen.getByText('$42,000')).toBeInTheDocument();
    });

    it('renders the value as number', () => {
      render(
        <KPICard
          title="Count"
          value={987}
          icon={<span data-testid="icon">📊</span>}
        />
      );
      expect(screen.getByText('987')).toBeInTheDocument();
    });

    it('renders the subtitle when provided', () => {
      render(
        <KPICard
          title="Tickets"
          value={100}
          subtitle="vs last month"
          icon={<span data-testid="icon">📋</span>}
        />
      );
      expect(screen.getByText('vs last month')).toBeInTheDocument();
    });

    it('renders the icon', () => {
      render(
        <KPICard
          title="Test"
          value={1}
          icon={<span data-testid="icon">🎯</span>}
        />
      );
      expect(screen.getByTestId('icon')).toBeInTheDocument();
    });

    it('renders with all props provided', () => {
      render(
        <KPICard
          title="CSAT Score"
          value="94.5%"
          subtitle="↑ from last week"
          icon={<span data-testid="icon">⭐</span>}
          trend={{ value: 12.5, label: 'vs last week' }}
          variant="success"
        />
      );
      expect(screen.getByText('CSAT Score')).toBeInTheDocument();
      expect(screen.getByText('94.5%')).toBeInTheDocument();
      expect(screen.getByText('↑ from last week')).toBeInTheDocument();
      expect(screen.getByText('12.5%')).toBeInTheDocument();
    });
  });

  // ── Variants ───────────────────────────────────────────────────────

  describe('Variants', () => {
    it('applies default variant styles', () => {
      const { container } = render(
        <KPICard
          title="Default"
          value={0}
          icon={<span>🔴</span>}
          variant="default"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-white/[0.06]');
    });

    it('applies success variant styles', () => {
      const { container } = render(
        <KPICard
          title="Success"
          value={100}
          icon={<span>✅</span>}
          variant="success"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-emerald-500/20');
    });

    it('applies warning variant styles', () => {
      const { container } = render(
        <KPICard
          title="Warning"
          value={50}
          icon={<span>⚠️</span>}
          variant="warning"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-amber-500/20');
    });

    it('applies danger variant styles', () => {
      const { container } = render(
        <KPICard
          title="Danger"
          value={3}
          icon={<span>🚨</span>}
          variant="danger"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-red-500/20');
    });

    it('applies info variant styles', () => {
      const { container } = render(
        <KPICard
          title="Info"
          value={7}
          icon={<span>ℹ️</span>}
          variant="info"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-sky-500/20');
    });
  });

  // ── Loading State ──────────────────────────────────────────────────

  describe('Loading State', () => {
    it('shows skeleton when isLoading is true', () => {
      const { container } = render(
        <KPICard
          title="Loading"
          value={0}
          icon={<span>🔄</span>}
          isLoading={true}
        />
      );
      // Skeleton uses animate-pulse
      expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('hides value when loading', () => {
      render(
        <KPICard
          title="Loading"
          value={999}
          icon={<span>🔄</span>}
          isLoading={true}
        />
      );
      expect(screen.queryByText('999')).not.toBeInTheDocument();
    });

    it('hides title when loading', () => {
      render(
        <KPICard
          title="Hidden"
          value={0}
          icon={<span>🔄</span>}
          isLoading={true}
        />
      );
      expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
    });

    it('shows icon placeholder when loading', () => {
      const { container } = render(
        <KPICard
          title="Loading"
          value={0}
          icon={<span data-testid="icon">🔄</span>}
          isLoading={true}
        />
      );
      // Icon placeholder is a rounded-lg with bg-white/[0.06]
      const placeholders = container.querySelectorAll('.rounded-lg.bg-white\\/\\[0\\.06\\]');
      expect(placeholders.length).toBeGreaterThanOrEqual(1);
    });

    it('applies variant styles to loading skeleton card', () => {
      const { container } = render(
        <KPICard
          title="Loading"
          value={0}
          icon={<span>🔄</span>}
          isLoading={true}
          variant="danger"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-red-500/20');
    });
  });

  // ── Trend Display ──────────────────────────────────────────────────

  describe('Trend Display', () => {
    it('renders positive trend with up arrow', () => {
      render(
        <KPICard
          title="Trend Up"
          value={100}
          icon={<span>📈</span>}
          trend={{ value: 15 }}
        />
      );
      expect(screen.getByText('15%')).toBeInTheDocument();
    });

    it('renders negative trend with down arrow (rotate-180)', () => {
      const { container } = render(
        <KPICard
          title="Trend Down"
          value={100}
          icon={<span>📉</span>}
          trend={{ value: -8.5 }}
        />
      );
      // Negative trend arrow has rotate-180
      const arrow = container.querySelector('.rotate-180');
      expect(arrow).toBeInTheDocument();
    });

    it('shows trend value as positive number even when negative', () => {
      render(
        <KPICard
          title="Trend"
          value={100}
          icon={<span>📊</span>}
          trend={{ value: -22 }}
        />
      );
      // Math.abs is used, so 22% should be displayed
      expect(screen.getByText('22%')).toBeInTheDocument();
    });

    it('positive trend has emerald color class', () => {
      const { container } = render(
        <KPICard
          title="Positive"
          value={100}
          icon={<span>📈</span>}
          trend={{ value: 5 }}
        />
      );
      expect(container.querySelector('.text-emerald-400')).toBeInTheDocument();
    });

    it('negative trend has red color class', () => {
      const { container } = render(
        <KPICard
          title="Negative"
          value={100}
          icon={<span>📉</span>}
          trend={{ value: -10 }}
        />
      );
      expect(container.querySelector('.text-red-400')).toBeInTheDocument();
    });

    it('zero trend has emerald color (treated as up)', () => {
      const { container } = render(
        <KPICard
          title="Zero"
          value={100}
          icon={<span>➡️</span>}
          trend={{ value: 0 }}
        />
      );
      expect(container.querySelector('.text-emerald-400')).toBeInTheDocument();
    });

    it('zero trend does not rotate arrow', () => {
      const { container } = render(
        <KPICard
          title="Zero"
          value={100}
          icon={<span>➡️</span>}
          trend={{ value: 0 }}
        />
      );
      expect(container.querySelector('.rotate-180')).not.toBeInTheDocument();
    });
  });

  // ── Without Optional Props ─────────────────────────────────────────

  describe('Without Optional Props', () => {
    it('does not render trend when not provided', () => {
      render(
        <KPICard
          title="No Trend"
          value={42}
          icon={<span>📊</span>}
        />
      );
      expect(screen.queryByText('%')).not.toBeInTheDocument();
    });

    it('does not render subtitle when not provided', () => {
      render(
        <KPICard
          title="No Subtitle"
          value={42}
          icon={<span>📊</span>}
        />
      );
      // Should only have title and value
      expect(screen.getByText('No Subtitle')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('defaults to default variant when variant not specified', () => {
      const { container } = render(
        <KPICard
          title="Default Variant"
          value={0}
          icon={<span>📋</span>}
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-white/[0.06]');
    });
  });

  // ── Custom className ───────────────────────────────────────────────

  describe('Custom className', () => {
    it('applies custom className to the card', () => {
      const { container } = render(
        <KPICard
          title="Custom"
          value={1}
          icon={<span>🎨</span>}
          className="my-custom-class"
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('my-custom-class');
    });

    it('applies custom className while loading', () => {
      const { container } = render(
        <KPICard
          title="Custom"
          value={1}
          icon={<span>🎨</span>}
          className="loading-class"
          isLoading={true}
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('loading-class');
    });
  });

  // ── Edge Cases ─────────────────────────────────────────────────────

  describe('Edge Cases', () => {
    it('renders with empty string value', () => {
      render(
        <KPICard
          title="Empty"
          value=""
          icon={<span>❓</span>}
        />
      );
      expect(screen.getByText('Empty')).toBeInTheDocument();
    });

    it('renders with zero value', () => {
      render(
        <KPICard
          title="Zero"
          value={0}
          icon={<span>0️⃣</span>}
        />
      );
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('renders with large trend value', () => {
      render(
        <KPICard
          title="Large Trend"
          value={999}
          icon={<span>🚀</span>}
          trend={{ value: 999.9 }}
        />
      );
      expect(screen.getByText('999.9%')).toBeInTheDocument();
    });

    it('renders with very small trend value', () => {
      render(
        <KPICard
          title="Small Trend"
          value={50}
          icon={<span>📏</span>}
          trend={{ value: 0.1 }}
        />
      );
      expect(screen.getByText('0.1%')).toBeInTheDocument();
    });

    it('card has rounded-xl and bg-[#1A1A1A] classes', () => {
      const { container } = render(
        <KPICard
          title="Styled"
          value={1}
          icon={<span>🎨</span>}
        />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('rounded-xl');
      expect(card.className).toContain('bg-[#1A1A1A]');
    });
  });
});
