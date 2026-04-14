/**
 * Week 16 Day 6 — Unit Tests: ROIDashboard (F-113)
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock recharts (includes SVG elements)
jest.mock('recharts', () => {
  const Original = jest.requireActual('recharts');
  return {
    ...Original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="rc">{children}</div>,
    AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="ac">{children}</div>,
    Area: () => null,
    BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bc">{children}</div>,
    Bar: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
    ReferenceLine: () => null,
    defs: () => null,
    linearGradient: () => null,
    stop: () => null,
  };
});

// Mock dashboardApi
jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getROIDashboard: jest.fn(),
    getConfidenceTrend: jest.fn(),
    getDriftReports: jest.fn(),
    getQAScores: jest.fn(),
    getGrowthNudges: jest.fn(),
    getTicketForecast: jest.fn(),
    getCSATTrends: jest.fn(),
    getHome: jest.fn(),
    getActivityFeed: jest.fn(),
    getMetrics: jest.fn(),
    getAdaptationTracker: jest.fn(),
  },
}));

import ROIDashboard from '@/components/dashboard/ROIDashboard';
import { dashboardApi } from '@/lib/dashboard-api';
import type { ROIDashboardResponse } from '@/lib/dashboard-api';

// ── Test Data ─────────────────────────────────────────────────────────

const generateROIData = (): ROIDashboardResponse => {
  const monthly_trend = [];
  let cumulative = 0;
  for (let i = 0; i < 12; i++) {
    const month = new Date('2025-05');
    month.setMonth(month.getMonth() + i);
    const period = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`;
    const ticketsAi = 400 + i * 60;
    const ticketsHuman = 200 - i * 10;
    const aiCost = ticketsAi * 0.15;
    const humanCost = ticketsHuman * 8.0;
    const savings = humanCost - aiCost;
    cumulative += savings;
    monthly_trend.push({
      period,
      date: `${period}-01`,
      tickets_ai: ticketsAi,
      tickets_human: Math.max(ticketsHuman, 50),
      ai_cost: aiCost,
      human_cost: humanCost,
      savings,
      cumulative_savings: cumulative,
    });
  }

  const current = monthly_trend[monthly_trend.length - 1];
  const previous = monthly_trend[monthly_trend.length - 2];

  return {
    current_month: {
      tickets_ai: current.tickets_ai,
      tickets_human: current.tickets_human,
      ai_cost: current.ai_cost,
      human_cost: current.human_cost,
      savings: current.savings,
      cumulative_savings: current.cumulative_savings,
      period: current.period,
      date: current.date,
    },
    previous_month: {
      tickets_ai: previous.tickets_ai,
      tickets_human: previous.tickets_human,
      ai_cost: previous.ai_cost,
      human_cost: previous.human_cost,
      savings: previous.savings,
      cumulative_savings: previous.cumulative_savings,
      period: previous.period,
      date: previous.date,
    },
    all_time_savings: cumulative,
    all_time_tickets_ai: monthly_trend.reduce((a, m) => a + m.tickets_ai, 0),
    all_time_tickets_human: monthly_trend.reduce((a, m) => a + m.tickets_human, 0),
    monthly_trend,
    avg_cost_per_ticket_ai: 0.15,
    avg_cost_per_ticket_human: 8.0,
    savings_pct: 96.2,
  };
};

// ══════════════════════════════════════════════════════════════════════
// F-113: ROIDashboard Tests
// ══════════════════════════════════════════════════════════════════════

describe('ROIDashboard Component (F-113)', () => {
  const mockData = generateROIData();

  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('ROI Dashboard')).toBeInTheDocument();
    });

    it('renders subtitle', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('AI cost savings & return on investment')).toBeInTheDocument();
    });

    it('renders all-time savings in header', () => {
      render(<ROIDashboard initialData={mockData} />);
      // cumulative savings is formatted in header
      expect(screen.getByText(/\$[\d,.]+K/)).toBeInTheDocument();
    });

    it('renders all 4 stat cards', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('This Month Savings')).toBeInTheDocument();
      expect(screen.getByText('AI Ticket Cost')).toBeInTheDocument();
      expect(screen.getByText('Human Ticket Cost')).toBeInTheDocument();
      expect(screen.getByText('Cost Ratio')).toBeInTheDocument();
    });

    it('renders AI ticket cost value', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('$0.15')).toBeInTheDocument();
    });

    it('renders human ticket cost value', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('$8.00')).toBeInTheDocument();
    });

    it('renders cost ratio with x cheaper label', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText(/cheaper/)).toBeInTheDocument();
    });

    it('renders bar chart section title', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('Monthly Cost Comparison: AI vs Human')).toBeInTheDocument();
    });

    it('renders cumulative savings section title', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(screen.getByText('Cumulative Savings Over Time')).toBeInTheDocument();
    });

    it('renders total AI tickets in subtext', () => {
      const { container } = render(<ROIDashboard initialData={mockData} />);
      expect(container.textContent).toContain('total AI');
    });

    it('renders total human tickets in subtext', () => {
      const { container } = render(<ROIDashboard initialData={mockData} />);
      expect(container.textContent).toContain('total human');
    });
  });

  describe('Accessibility', () => {
    it('has role=img with aria-label on bar chart', () => {
      render(<ROIDashboard initialData={mockData} />);
      const charts = screen.getAllByRole('img');
      expect(charts[0]).toHaveAttribute('aria-label', 'Monthly AI vs human cost comparison bar chart');
    });

    it('has role=img with aria-label on cumulative chart', () => {
      render(<ROIDashboard initialData={mockData} />);
      const charts = screen.getAllByRole('img');
      expect(charts[1]).toHaveAttribute('aria-label', 'Cumulative savings trend chart');
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when isLoading is true', () => {
      const { container } = render(<ROIDashboard isLoading />);
      expect(screen.queryByText('ROI Dashboard')).not.toBeInTheDocument();
      expect(container.querySelector('[class*=bg-white]')).toBeTruthy();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no monthly trend', () => {
      const emptyData = {
        ...mockData,
        monthly_trend: [],
        all_time_savings: 0,
        all_time_tickets_ai: 0,
        all_time_tickets_human: 0,
      };
      render(<ROIDashboard initialData={emptyData} />);
      expect(screen.getByText('No ROI data yet')).toBeInTheDocument();
    });

    it('renders header even when empty', () => {
      const emptyData = { ...mockData, monthly_trend: [], all_time_savings: 0, all_time_tickets_ai: 0, all_time_tickets_human: 0 };
      render(<ROIDashboard initialData={emptyData} />);
      expect(screen.getByText('ROI Dashboard')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getROIDashboard as jest.Mock).mockResolvedValue(mockData);
      render(<ROIDashboard />);
      await waitFor(() => expect(dashboardApi.getROIDashboard).toHaveBeenCalledWith(12));
    });

    it('does not fetch with initialData', () => {
      render(<ROIDashboard initialData={mockData} />);
      expect(dashboardApi.getROIDashboard).not.toHaveBeenCalled();
    });

    it('handles API error gracefully', async () => {
      (dashboardApi.getROIDashboard as jest.Mock).mockRejectedValue(new Error('Network error'));
      render(<ROIDashboard />);
      await waitFor(() => expect(dashboardApi.getROIDashboard).toHaveBeenCalled());
      await waitFor(() => expect(screen.getByText('No ROI data yet')).toBeInTheDocument());
    });
  });

  describe('Edge Cases', () => {
    it('handles zero AI cost without division by zero', () => {
      const zeroAiCost = { ...mockData, avg_cost_per_ticket_ai: 0 };
      render(<ROIDashboard initialData={zeroAiCost} />);
      expect(screen.getByText('Cost Ratio')).toBeInTheDocument();
    });

    it('handles zero total tickets gracefully', () => {
      const noTickets = { ...mockData, all_time_tickets_ai: 0, all_time_tickets_human: 0 };
      render(<ROIDashboard initialData={noTickets} />);
      expect(screen.getByText('0% resolved by AI')).toBeInTheDocument();
    });

    it('formats large savings amounts with K suffix', () => {
      render(<ROIDashboard initialData={mockData} />);
      // All-time savings should be formatted
      const { container } = render(<ROIDashboard initialData={mockData} />);
      expect(container.textContent).toContain('K');
    });
  });
});
