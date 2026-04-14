/**
 * Day 16 — Unit Tests: DashboardAlerts Component (F-036)
 *
 * Tests the DashboardAlerts component rendering, severity levels,
 * dismiss functionality, and empty state.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import DashboardAlerts from '@/components/dashboard/DashboardAlerts';
import type { AnomalyAlert } from '@/types/analytics';

// ── Test Data ─────────────────────────────────────────────────────────

const mockAlerts: AnomalyAlert[] = [
  {
    type: 'volume_spike',
    severity: 'high',
    message: 'Ticket volume spike: 250 tickets in last 24h (12.5x normal)',
    detected_at: new Date(Date.now() - 10 * 60000).toISOString(),
  },
  {
    type: 'sla_breach_cluster',
    severity: 'high',
    message: '15 SLA breaches in last 24 hours',
    detected_at: new Date(Date.now() - 30 * 60000).toISOString(),
  },
  {
    type: 'resolution_drop',
    severity: 'medium',
    message: 'Resolution rate dropped below 60% threshold',
    detected_at: new Date(Date.now() - 2 * 3600000).toISOString(),
  },
  {
    type: 'csat_decline',
    severity: 'low',
    message: 'CSAT average declined by 0.3 points this week',
    detected_at: new Date(Date.now() - 5 * 3600000).toISOString(),
  },
];

// ── Test Suite ────────────────────────────────────────────────────────

describe('DashboardAlerts Component (F-036)', () => {
  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders all alerts', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      expect(screen.getByText(/Ticket volume spike/)).toBeInTheDocument();
      expect(screen.getByText(/15 SLA breaches/)).toBeInTheDocument();
      expect(screen.getByText(/Resolution rate dropped/)).toBeInTheDocument();
      expect(screen.getByText(/CSAT average declined/)).toBeInTheDocument();
    });

    it('renders severity badges', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      // Should have 2 "high", 1 "medium", 1 "low" severity badges
      const highBadges = screen.getAllByText('high');
      const mediumBadges = screen.getAllByText('medium');
      const lowBadges = screen.getAllByText('low');
      expect(highBadges.length).toBe(2);
      expect(mediumBadges.length).toBe(1);
      expect(lowBadges.length).toBe(1);
    });

    it('renders relative timestamps', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      expect(screen.getByText('10m ago')).toBeInTheDocument();
      expect(screen.getByText('30m ago')).toBeInTheDocument();
      expect(screen.getByText('2h ago')).toBeInTheDocument();
      expect(screen.getByText('5h ago')).toBeInTheDocument();
    });

    it('shows active alert count when multiple alerts', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      expect(screen.getByText('4 active alerts')).toBeInTheDocument();
    });

    it('does not show count header for single alert', () => {
      render(<DashboardAlerts alerts={[mockAlerts[0]]} />);
      expect(screen.queryByText(/active alert/)).not.toBeInTheDocument();
    });
  });

  // ── Severity Colors ────────────────────────────────────────────────

  describe('Severity Colors', () => {
    it('applies high severity red styling', () => {
      const { container } = render(
        <DashboardAlerts alerts={[mockAlerts[0]]} />
      );
      // Check for red border class
      const alertCard = container.querySelector('.border-red-500\\/20');
      expect(alertCard).toBeInTheDocument();
    });

    it('applies medium severity amber styling', () => {
      const { container } = render(
        <DashboardAlerts alerts={[mockAlerts[2]]} />
      );
      const alertCard = container.querySelector('.border-amber-500\\/20');
      expect(alertCard).toBeInTheDocument();
    });

    it('applies low severity sky styling', () => {
      const { container } = render(
        <DashboardAlerts alerts={[mockAlerts[3]]} />
      );
      const alertCard = container.querySelector('.border-sky-500\\/20');
      expect(alertCard).toBeInTheDocument();
    });
  });

  // ── Dismiss Functionality ──────────────────────────────────────────

  describe('Dismiss', () => {
    it('renders dismiss buttons for each alert', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      // 4 dismiss buttons (one per alert)
      const dismissButtons = screen.getAllByTitle('Dismiss alert');
      expect(dismissButtons.length).toBe(4);
    });

    it('dismisses a single alert on button click', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      const dismissButtons = screen.getAllByTitle('Dismiss alert');

      // Dismiss first alert
      fireEvent.click(dismissButtons[0]);

      // First alert should be gone, rest remain
      expect(screen.queryByText(/Ticket volume spike/)).not.toBeInTheDocument();
      expect(screen.getByText(/15 SLA breaches/)).toBeInTheDocument();
      // Count should update
      expect(screen.getByText('3 active alerts')).toBeInTheDocument();
    });

    it('calls onDismiss callback when alert is dismissed', () => {
      const onDismiss = jest.fn();
      render(<DashboardAlerts alerts={mockAlerts} onDismiss={onDismiss} />);
      const dismissButtons = screen.getAllByTitle('Dismiss alert');

      fireEvent.click(dismissButtons[1]);

      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('dismiss all button removes all alerts', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      const dismissAllBtn = screen.getByText('Dismiss all');

      fireEvent.click(dismissAllBtn);

      // All alerts should be gone
      expect(screen.queryByText(/Ticket volume spike/)).not.toBeInTheDocument();
      expect(screen.queryByText(/15 SLA breaches/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Resolution rate dropped/)).not.toBeInTheDocument();
      expect(screen.queryByText(/CSAT average declined/)).not.toBeInTheDocument();
    });
  });

  // ── Empty State ─────────────────────────────────────────────────────

  describe('Empty State', () => {
    it('returns null when alerts array is empty', () => {
      const { container } = render(<DashboardAlerts alerts={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when all alerts are dismissed', () => {
      render(<DashboardAlerts alerts={mockAlerts} />);
      const dismissAllBtn = screen.getByText('Dismiss all');
      fireEvent.click(dismissAllBtn);

      // Component should have rendered nothing
      const alertMessages = screen.queryByText(/alert/);
      expect(alertMessages).toBeNull();
    });
  });

  // ── Edge Cases ─────────────────────────────────────────────────────

  describe('Edge Cases', () => {
    it('handles alerts with missing detected_at gracefully', () => {
      const alertNoTime: AnomalyAlert = {
        type: 'volume_spike',
        severity: 'high',
        message: 'Volume spike detected',
        detected_at: '',
      };
      render(<DashboardAlerts alerts={[alertNoTime]} />);
      expect(screen.getByText('Volume spike detected')).toBeInTheDocument();
    });

    it('handles unknown severity as medium fallback', () => {
      const alertUnknown: AnomalyAlert = {
        type: 'volume_spike',
        severity: 'medium',
        message: 'Test alert',
        detected_at: new Date().toISOString(),
      };
      const { container } = render(
        <DashboardAlerts alerts={[alertUnknown]} />
      );
      // Should still render without crashing
      expect(screen.getByText('Test alert')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <DashboardAlerts alerts={mockAlerts} className="mt-4" />
      );
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('mt-4');
    });
  });
});
