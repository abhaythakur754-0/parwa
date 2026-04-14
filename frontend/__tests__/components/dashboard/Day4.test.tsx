/**
 * Week 16 Day 4 — Unit Tests: GrowthNudge (F-042), TicketForecast (F-043), CSATTrends (F-044)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock recharts
jest.mock('recharts', () => {
  const Original = jest.requireActual('recharts');
  return {
    ...Original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="rc">{children}</div>,
    AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="ac">{children}</div>,
    Area: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
    ReferenceLine: () => null,
  };
});

// Mock dashboardApi
jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getGrowthNudges: jest.fn(),
    getTicketForecast: jest.fn(),
    getCSATTrends: jest.fn(),
    getHome: jest.fn(),
    getActivityFeed: jest.fn(),
    getMetrics: jest.fn(),
    getAdaptationTracker: jest.fn(),
  },
}));

import GrowthNudge from '@/components/dashboard/GrowthNudge';
import TicketForecast from '@/components/dashboard/TicketForecast';
import CSATTrends from '@/components/dashboard/CSATTrends';
import { dashboardApi } from '@/lib/dashboard-api';
import type { GrowthNudgeResponse, TicketForecastResponse, CSATTrendsResponse } from '@/lib/dashboard-api';

// ── F-042 Test Data ───────────────────────────────────────────────────

const mockNudgeData: GrowthNudgeResponse = {
  nudges: [
    {
      nudge_id: 'nudge-1',
      nudge_type: 'underutilized',
      severity: 'urgent',
      title: 'SLA breach rate is high',
      message: '15 of 50 tickets (30.0%) breached SLA this week.',
      action_label: 'Review SLA Settings',
      action_url: '/settings/sla',
      dismissed: false,
      detected_at: '2026-04-15T10:00:00Z',
    },
    {
      nudge_id: 'nudge-2',
      nudge_type: 'scaling',
      severity: 'recommendation',
      title: 'Ticket volume is growing fast',
      message: 'Volume increased from 80 to 130 tickets/week (+63%).',
      action_label: 'View Plans',
      action_url: '/billing/plans',
      dismissed: false,
      detected_at: '2026-04-15T10:00:00Z',
    },
    {
      nudge_id: 'nudge-3',
      nudge_type: 'feature_discovery',
      severity: 'info',
      title: 'WhatsApp channel has no recent activity',
      message: 'No tickets received via WhatsApp in the last 7 days.',
      action_label: 'Configure Channel',
      action_url: '/settings/channels/whatsapp',
      dismissed: false,
      detected_at: '2026-04-15T10:00:00Z',
    },
  ],
  total: 3,
  dismissed_count: 0,
};

// ── F-043 Test Data ───────────────────────────────────────────────────

const generateForecastData = (): TicketForecastResponse => {
  const historical = [];
  const forecast = [];
  for (let i = 0; i < 30; i++) {
    const date = new Date('2026-03-16');
    date.setDate(date.getDate() + i);
    historical.push({ date: date.toISOString().split('T')[0], predicted: 40 + Math.round(Math.sin(i / 5) * 10), actual: 40 + Math.round(Math.sin(i / 5) * 10) });
  }
  for (let i = 0; i < 14; i++) {
    const date = new Date('2026-04-15');
    date.setDate(date.getDate() + i + 1);
    forecast.push({ date: date.toISOString().split('T')[0], predicted: 45 + i, lower_bound: 35 + i, upper_bound: 55 + i });
  }
  return { historical, forecast, model_type: 'linear_regression', confidence_level: 0.95, seasonality_detected: true, trend_direction: 'increasing', avg_daily_volume: 42.3 };
};

// ── F-044 Test Data ───────────────────────────────────────────────────

const generateCSATData = (): CSATTrendsResponse => {
  const daily_trend = [];
  for (let i = 0; i < 30; i++) {
    const date = new Date('2026-03-16');
    date.setDate(date.getDate() + i);
    daily_trend.push({
      date: date.toISOString().split('T')[0],
      avg_rating: 3.5 + (i / 29) * 0.5,
      total_ratings: 10 + i,
      distribution: { '5': Math.floor(i / 5) + 2, '4': Math.floor(i / 3) + 3, '3': 3, '2': 1, '1': 0 },
    });
  }
  return {
    daily_trend,
    overall_avg: 4.0,
    overall_total: 695,
    by_agent: [{ dimension_name: 'AI Agent', avg_rating: 4.2, total_ratings: 300 }, { dimension_name: 'Sarah', avg_rating: 3.8, total_ratings: 200 }],
    by_category: [{ dimension_name: 'Billing', avg_rating: 3.5, total_ratings: 150 }],
    by_channel: [{ dimension_name: 'email', avg_rating: 4.1, total_ratings: 400 }],
    trend_direction: 'improving',
    change_vs_previous_period: 0.32,
  };
};

// ══════════════════════════════════════════════════════════════════════
// F-042: GrowthNudge Tests
// ══════════════════════════════════════════════════════════════════════

describe('GrowthNudge Component (F-042)', () => {
  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders the header title', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(screen.getByText('Growth Insights')).toBeInTheDocument();
    });

    it('renders all nudge titles', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(screen.getByText('SLA breach rate is high')).toBeInTheDocument();
      expect(screen.getByText('Ticket volume is growing fast')).toBeInTheDocument();
      expect(screen.getByText('WhatsApp channel has no recent activity')).toBeInTheDocument();
    });

    it('renders severity badges', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(screen.getByText('Urgent')).toBeInTheDocument();
      expect(screen.getByText('Recommendation')).toBeInTheDocument();
      expect(screen.getByText('Info')).toBeInTheDocument();
    });

    it('renders action buttons', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(screen.getByText('Review SLA Settings')).toBeInTheDocument();
      expect(screen.getByText('View Plans')).toBeInTheDocument();
      expect(screen.getByText('Configure Channel')).toBeInTheDocument();
    });

    it('renders nudge count badge', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(screen.getByText('3 nudges')).toBeInTheDocument();
    });
  });

  describe('Dismiss', () => {
    it('dismisses a nudge card on click', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      const dismissBtns = screen.getAllByText('Dismiss');
      fireEvent.click(dismissBtns[0]);
      expect(screen.queryByText('SLA breach rate is high')).not.toBeInTheDocument();
    });

    it('shows empty state when all dismissed', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      const dismissBtns = screen.getAllByText('Dismiss');
      dismissBtns.forEach((btn) => fireEvent.click(btn));
      expect(screen.getByText('All good!')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no nudges', () => {
      render(<GrowthNudge initialData={{ nudges: [], total: 0, dismissed_count: 0 }} />);
      expect(screen.getByText('All good!')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getGrowthNudges as jest.Mock).mockResolvedValue(mockNudgeData);
      render(<GrowthNudge />);
      await waitFor(() => expect(dashboardApi.getGrowthNudges).toHaveBeenCalled());
    });

    it('does not fetch with initialData', () => {
      render(<GrowthNudge initialData={mockNudgeData} />);
      expect(dashboardApi.getGrowthNudges).not.toHaveBeenCalled();
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// F-043: TicketForecast Tests
// ══════════════════════════════════════════════════════════════════════

describe('TicketForecast Component (F-043)', () => {
  const mockForecast = generateForecastData();

  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('Ticket Forecast')).toBeInTheDocument();
    });

    it('renders trend badge', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('Trending Up')).toBeInTheDocument();
    });

    it('renders metric cards', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('Avg Daily')).toBeInTheDocument();
      expect(screen.getByText('Model')).toBeInTheDocument();
      expect(screen.getByText('Seasonality')).toBeInTheDocument();
    });

    it('shows seasonality detected', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('Detected')).toBeInTheDocument();
    });

    it('shows linear regression model', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('linear regression')).toBeInTheDocument();
    });

    it('shows 95% confidence', () => {
      render(<TicketForecast initialData={mockForecast} />);
      expect(screen.getByText('95% confidence')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no data', () => {
      render(<TicketForecast initialData={{ historical: [], forecast: [], model_type: 'none', confidence_level: 0.95, seasonality_detected: false, trend_direction: 'stable', avg_daily_volume: 0 }} />);
      expect(screen.getByText('No forecast data')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getTicketForecast as jest.Mock).mockResolvedValue(mockForecast);
      render(<TicketForecast />);
      await waitFor(() => expect(dashboardApi.getTicketForecast).toHaveBeenCalledWith(14, 30));
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// F-044: CSATTrends Tests
// ══════════════════════════════════════════════════════════════════════

describe('CSATTrends Component (F-044)', () => {
  const mockCSAT = generateCSATData();

  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      expect(screen.getByText('CSAT Trends')).toBeInTheDocument();
    });

    it('renders overall average', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      expect(screen.getByText('4.0')).toBeInTheDocument();
    });

    it('renders total ratings', () => {
      const { container } = render(<CSATTrends initialData={mockCSAT} />);
      expect(container.textContent).toContain('695 ratings');
    });

    it('renders dimension tabs', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      expect(screen.getByText('By Agent')).toBeInTheDocument();
      expect(screen.getByText('By Category')).toBeInTheDocument();
      expect(screen.getByText('By Channel')).toBeInTheDocument();
    });

    it('renders rating distribution', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      expect(screen.getByText('Rating Distribution')).toBeInTheDocument();
    });

    it('renders change vs previous period', () => {
      const { container } = render(<CSATTrends initialData={mockCSAT} />);
      expect(container.textContent).toContain('+0.32 vs prev');
    });

    it('renders dimension breakdown by default (agent)', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      expect(screen.getByText('AI Agent')).toBeInTheDocument();
      expect(screen.getByText('Sarah')).toBeInTheDocument();
    });
  });

  describe('Dimension Tabs', () => {
    it('switches to category tab', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      fireEvent.click(screen.getByText('By Category'));
      expect(screen.getByText('Billing')).toBeInTheDocument();
    });

    it('switches to channel tab', () => {
      render(<CSATTrends initialData={mockCSAT} />);
      fireEvent.click(screen.getByText('By Channel'));
      expect(screen.getByText('email')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no data', () => {
      render(<CSATTrends initialData={{ daily_trend: [], overall_avg: 0, overall_total: 0, by_agent: [], by_category: [], by_channel: [], trend_direction: 'stable', change_vs_previous_period: null }} />);
      expect(screen.getByText('No CSAT data yet')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getCSATTrends as jest.Mock).mockResolvedValue(mockCSAT);
      render(<CSATTrends />);
      await waitFor(() => expect(dashboardApi.getCSATTrends).toHaveBeenCalledWith(30));
    });
  });
});
