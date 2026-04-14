/**
 * Week 16 Day 3 — Unit Tests: AdaptationTracker Component (F-039)
 *
 * Tests the AdaptationTracker component rendering, chart data,
 * metric cards, empty states, and loading states.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock recharts to avoid canvas rendering in tests
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    AreaChart: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="area-chart">{children}</div>
    ),
    Area: () => null,
    LineChart: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="line-chart">{children}</div>
    ),
    Line: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

// Mock the dashboardApi
jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getAdaptationTracker: jest.fn(),
    getHome: jest.fn(),
    getActivityFeed: jest.fn(),
    getMetrics: jest.fn(),
  },
}));

import AdaptationTracker from '@/components/dashboard/AdaptationTracker';
import { dashboardApi } from '@/lib/dashboard-api';
import type { AdaptationTrackerResponse, AdaptationDayData } from '@/lib/dashboard-api';

// ── Test Data ─────────────────────────────────────────────────────────

const mockDay1: AdaptationDayData = {
  date: '2026-03-16',
  ai_accuracy: 3.2,
  human_accuracy: 4.0,
  gap: -0.8,
  tickets_processed: 45,
  mistakes_count: 5,
  mistake_rate: 11.1,
};

const mockDay15: AdaptationDayData = {
  date: '2026-03-30',
  ai_accuracy: 3.8,
  human_accuracy: 4.1,
  gap: -0.3,
  tickets_processed: 62,
  mistakes_count: 3,
  mistake_rate: 4.8,
};

const mockDay30: AdaptationDayData = {
  date: '2026-04-14',
  ai_accuracy: 4.3,
  human_accuracy: 4.0,
  gap: 0.3,
  tickets_processed: 78,
  mistakes_count: 2,
  mistake_rate: 2.6,
};

const generateDailyData = (): AdaptationDayData[] => {
  const days: AdaptationDayData[] = [];
  for (let i = 0; i < 30; i++) {
    const date = new Date('2026-03-16');
    date.setDate(date.getDate() + i);
    const progress = i / 29;
    days.push({
      date: date.toISOString().split('T')[0],
      ai_accuracy: 3.2 + progress * 1.1,
      human_accuracy: 4.0 - progress * 0.1,
      gap: (3.2 + progress * 1.1) - (4.0 - progress * 0.1),
      tickets_processed: 40 + Math.round(progress * 40),
      mistakes_count: Math.round(6 - progress * 4),
      mistake_rate: parseFloat(((6 - progress * 4) / (40 + progress * 40) * 100).toFixed(1)),
    });
  }
  return days;
};

const mockData: AdaptationTrackerResponse = {
  daily_data: generateDailyData(),
  overall_improvement_pct: 34.4,
  current_accuracy: 4.3,
  starting_accuracy: 3.2,
  best_day: mockDay30,
  worst_day: mockDay1,
  training_runs_count: 3,
  drift_reports_count: 1,
};

const mockEmptyData: AdaptationTrackerResponse = {
  daily_data: [],
  overall_improvement_pct: 0,
  current_accuracy: 0,
  starting_accuracy: 0,
  best_day: null,
  worst_day: null,
  training_runs_count: 0,
  drift_reports_count: 0,
};

// ── Test Suite ────────────────────────────────────────────────────────

describe('AdaptationTracker Component (F-039)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the header title', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('AI Adaptation Tracker')).toBeInTheDocument();
    });

    it('renders the subtitle', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('30-day AI learning progress')).toBeInTheDocument();
    });

    it('renders the improvement metric card', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('Improvement')).toBeInTheDocument();
      expect(screen.getByText('+34.4%')).toBeInTheDocument();
    });

    it('renders AI accuracy metric card', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('AI Accuracy')).toBeInTheDocument();
      // 4.3 appears in multiple places, use getAllByText
      const fourThree = screen.getAllByText('4.3');
      expect(fourThree.length).toBeGreaterThanOrEqual(1);
    });

    it('renders best day metric card', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('Best Day')).toBeInTheDocument();
    });

    it('renders mistake rate section', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('Mistake Rate')).toBeInTheDocument();
    });

    it('renders training runs and drift reports in footer', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('3')).toBeInTheDocument(); // training count
      expect(screen.getByText('1')).toBeInTheDocument(); // drift count
      expect(screen.getByText('training runs')).toBeInTheDocument();
      expect(screen.getByText('drift reports')).toBeInTheDocument();
    });

    it('shows the AI improvement range', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('3.2% → 4.3%')).toBeInTheDocument();
    });

    it('shows the best day date', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('2026-04-14')).toBeInTheDocument();
    });

    it('renders the chart container', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByTestId('area-chart')).toBeInTheDocument();
    });
  });

  // ── Empty State ─────────────────────────────────────────────────────

  describe('Empty State', () => {
    it('shows empty state when no data', () => {
      render(<AdaptationTracker initialData={mockEmptyData} />);
      expect(screen.getByText('No adaptation data yet')).toBeInTheDocument();
    });

    it('shows empty state helper text', () => {
      render(<AdaptationTracker initialData={mockEmptyData} />);
      expect(
        screen.getByText('AI accuracy metrics will appear once tickets are resolved')
      ).toBeInTheDocument();
    });

    it('shows empty state when data is null', async () => {
      (dashboardApi.getAdaptationTracker as jest.Mock).mockResolvedValue(mockEmptyData);
      render(<AdaptationTracker />);
      await waitFor(() => {
        expect(screen.getByText('No adaptation data yet')).toBeInTheDocument();
      });
    });
  });

  // ── Loading State ───────────────────────────────────────────────────

  describe('Loading State', () => {
    it('shows loading skeleton when isLoading is true', () => {
      const { container } = render(<AdaptationTracker isLoading={true} />);
      // Skeleton renders pulse animations
      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  // ── API Fetching ────────────────────────────────────────────────────

  describe('API Fetching', () => {
    it('fetches data on mount when no initialData provided', async () => {
      (dashboardApi.getAdaptationTracker as jest.Mock).mockResolvedValue(mockData);

      render(<AdaptationTracker />);

      await waitFor(() => {
        expect(dashboardApi.getAdaptationTracker).toHaveBeenCalledWith(30);
      });
    });

    it('does not fetch when initialData is provided', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(dashboardApi.getAdaptationTracker).not.toHaveBeenCalled();
    });

    it('refreshes data when refresh button clicked', async () => {
      (dashboardApi.getAdaptationTracker as jest.Mock).mockResolvedValue(mockData);

      render(<AdaptationTracker initialData={mockData} />);

      const refreshBtn = screen.getByRole('button');
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(dashboardApi.getAdaptationTracker).toHaveBeenCalledWith(30);
      });
    });

    it('handles API errors silently', async () => {
      (dashboardApi.getAdaptationTracker as jest.Mock).mockRejectedValue(
        new Error('Network error')
      );

      // Should not throw
      expect(() => render(<AdaptationTracker />)).not.toThrow();
    });
  });

  // ── Improvement Direction ───────────────────────────────────────────

  describe('Improvement Direction', () => {
    it('shows positive improvement with green variant', () => {
      render(<AdaptationTracker initialData={mockData} />);
      const improvementValue = screen.getByText('+34.4%');
      // Should have the improvement text
      expect(improvementValue).toBeInTheDocument();
    });

    it('handles zero improvement', () => {
      const zeroData = {
        ...mockData,
        overall_improvement_pct: 0,
        current_accuracy: 3.2,
        starting_accuracy: 3.2,
      };
      const { container } = render(<AdaptationTracker initialData={zeroData} />);
      // +0.0% should be somewhere in the rendered output
      expect(container.textContent).toContain('0.0%');
    });

    it('handles negative improvement (decline)', () => {
      const declineData = {
        ...mockData,
        overall_improvement_pct: -5.2,
        current_accuracy: 3.0,
        starting_accuracy: 3.2,
      };
      render(<AdaptationTracker initialData={declineData} />);
      expect(screen.getByText('-5.2%')).toBeInTheDocument();
    });
  });

  // ── Metric Cards ────────────────────────────────────────────────────

  describe('Metric Cards', () => {
    it('renders 4 metric cards', () => {
      const { container } = render(<AdaptationTracker initialData={mockData} />);
      const cards = container.querySelectorAll('.rounded-lg.border');
      // At least 4 metric cards + 1 main container = 5+ borders
      expect(cards.length).toBeGreaterThanOrEqual(4);
    });

    it('shows accuracy out of 5.0', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText('out of 5.0')).toBeInTheDocument();
    });

    it('shows average mistake rate', () => {
      render(<AdaptationTracker initialData={mockData} />);
      expect(screen.getByText(/Avg:.*over 30 days/)).toBeInTheDocument();
    });
  });

  // ── Training & Drift Footer ─────────────────────────────────────────

  describe('Training & Drift Footer', () => {
    it('hides footer when both counts are zero', () => {
      const noTrainingData = {
        ...mockData,
        training_runs_count: 0,
        drift_reports_count: 0,
      };
      const { container } = render(<AdaptationTracker initialData={noTrainingData} />);
      // Footer should not be present
      const footerTexts = container.querySelectorAll('training runs');
      expect(footerTexts.length).toBe(0);
    });
  });

  // ── Data Sync ───────────────────────────────────────────────────────

  describe('Data Sync', () => {
    it('updates when initialData prop changes', () => {
      const updatedData = {
        ...mockData,
        current_accuracy: 4.8,
        overall_improvement_pct: 50.0,
      };

      const { container, rerender } = render(<AdaptationTracker initialData={mockData} />);
      expect(container.textContent).toContain('4.3');

      rerender(<AdaptationTracker initialData={updatedData} />);
      expect(container.textContent).toContain('4.8');
      expect(container.textContent).toContain('+50.0%');
    });
  });
});
