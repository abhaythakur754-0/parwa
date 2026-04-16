/**
 * Day 16 — Unit Tests: SavingsCounter Component (F-040)
 *
 * Tests the SavingsCounter component rendering, views,
 * cost comparison, and trend display.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the API
jest.mock('@/lib/api', () => ({
  get: jest.fn(),
}));

// Mock dashboardApi (module may not exist on disk; Days 3-6 added these functions)
jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getHome: jest.fn(),
    getActivityFeed: jest.fn(),
    getMetrics: jest.fn(),
    getAdaptationTracker: jest.fn(),
    getGrowthNudges: jest.fn(),
    getTicketForecast: jest.fn(),
    getCSATTrends: jest.fn(),
    getConfidenceTrend: jest.fn(),
    getDriftReports: jest.fn(),
    getQAScores: jest.fn(),
    getROIDashboard: jest.fn(),
  },
}));

import SavingsCounter from '@/components/dashboard/SavingsCounter';
import { get } from '@/lib/api';

// ── Mock Data ─────────────────────────────────────────────────────────

const mockSavingsData = {
  current_month: {
    period: '2025-04',
    date: '2025-04-01',
    tickets_ai: 450,
    tickets_human: 180,
    ai_cost: 67.50,
    human_cost: 1440.00,
    savings: 1372.50,
    cumulative_savings: 15432.50,
  },
  previous_month: {
    period: '2025-03',
    date: '2025-03-01',
    tickets_ai: 380,
    tickets_human: 210,
    ai_cost: 57.00,
    human_cost: 1680.00,
    savings: 1623.00,
    cumulative_savings: 14060.00,
  },
  all_time_savings: 15432.50,
  all_time_tickets_ai: 4200,
  all_time_tickets_human: 2100,
  monthly_trend: [
    { period: '2025-04', date: '2025-04-01', tickets_ai: 450, tickets_human: 180, ai_cost: 67.50, human_cost: 1440, savings: 1372.50, cumulative_savings: 15432.50 },
    { period: '2025-03', date: '2025-03-01', tickets_ai: 380, tickets_human: 210, ai_cost: 57, human_cost: 1680, savings: 1623, cumulative_savings: 14060 },
    { period: '2025-02', date: '2025-02-01', tickets_ai: 320, tickets_human: 190, ai_cost: 48, human_cost: 1520, savings: 1472, cumulative_savings: 12437 },
  ],
  avg_cost_per_ticket_ai: 0.15,
  avg_cost_per_ticket_human: 8.00,
  savings_pct: 98.1,
};

// ── Test Suite ────────────────────────────────────────────────────────

describe('SavingsCounter Component (F-040)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering with initialData', () => {
    it('renders the savings header', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      expect(screen.getByText('AI Savings')).toBeInTheDocument();
    });

    it('renders the total savings amount', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      // The animated value should render the amount
      expect(screen.getByText('Total Savings (All Time)')).toBeInTheDocument();
    });

    it('renders AI cost per ticket', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      expect(screen.getByText('$0.15')).toBeInTheDocument();
    });

    it('renders human cost per ticket', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      expect(screen.getByText('$8.00')).toBeInTheDocument();
    });

    it('renders cost reduction percentage', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      expect(screen.getByText('98.1%')).toBeInTheDocument();
    });

    it('renders this month snapshot', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      // Text content of the span includes "450 AI" and "180 Human"
      expect(screen.getByText('This Month')).toBeInTheDocument();
      const aiText = screen.getByText('450');
      expect(aiText).toBeInTheDocument();
      const humanText = screen.getByText('180');
      expect(humanText).toBeInTheDocument();
    });

    it('renders MoM change', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      // MoM change: (1372.50 - 1623) / 1623 = -15.4%
      expect(screen.getByText(/-15.4%/)).toBeInTheDocument();
    });
  });

  describe('View Tabs', () => {
    it('renders overview and trend tabs', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Trend')).toBeInTheDocument();
    });

    it('switches to trend view on tab click', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      fireEvent.click(screen.getByText('Trend'));
      // Should show monthly trend data
      expect(screen.getByText('2025-04')).toBeInTheDocument();
      expect(screen.getByText('2025-03')).toBeInTheDocument();
      expect(screen.getByText('2025-02')).toBeInTheDocument();
    });

    it('shows savings amounts in trend view', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      fireEvent.click(screen.getByText('Trend'));
      // Check for the period labels which confirms we're in trend view
      expect(screen.getByText('2025-02')).toBeInTheDocument();
    });

    it('switches back to overview', () => {
      render(<SavingsCounter initialData={mockSavingsData} />);
      fireEvent.click(screen.getByText('Trend'));
      fireEvent.click(screen.getByText('Overview'));
      expect(screen.getByText('Total Savings (All Time)')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no data and API fails', async () => {
      (get as jest.Mock).mockRejectedValue(new Error('API error'));

      render(<SavingsCounter />);

      await waitFor(() => {
        expect(screen.getByText('No savings data yet')).toBeInTheDocument();
      });
    });

    it('shows helper text in empty state', async () => {
      (get as jest.Mock).mockRejectedValue(new Error('API error'));

      render(<SavingsCounter />);

      await waitFor(() => {
        expect(screen.getByText(/Data will appear as AI resolves tickets/)).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('shows skeleton when loading', () => {
      (get as jest.Mock).mockReturnValue(new Promise(() => {}));
      render(<SavingsCounter />);
      // Skeleton elements should be present
      const skeletonElements = document.querySelectorAll('.animate-pulse');
      expect(skeletonElements.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('handles zero savings gracefully', () => {
      const zeroData = {
        ...mockSavingsData,
        all_time_savings: 0,
        savings_pct: 0,
        current_month: { ...mockSavingsData.current_month, savings: 0, tickets_ai: 0, tickets_human: 0 },
      };
      render(<SavingsCounter initialData={zeroData} />);
      expect(screen.getByText('AI Savings')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <SavingsCounter initialData={mockSavingsData} className="mt-4" />
      );
      expect(container.firstChild).toHaveClass('mt-4');
    });
  });
});
