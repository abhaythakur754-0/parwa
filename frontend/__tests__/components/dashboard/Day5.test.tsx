/**
 * Week 16 Day 5 — Unit Tests: ConfidenceTrend (F-115), DriftDetection (F-116), QAScores (F-119)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock recharts (includes SVG elements to avoid console warnings)
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
    defs: () => null,
    linearGradient: () => null,
    stop: () => null,
  };
});

// Mock dashboardApi
jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
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

import ConfidenceTrend from '@/components/dashboard/ConfidenceTrend';
import DriftDetection from '@/components/dashboard/DriftDetection';
import QAScores from '@/components/dashboard/QAScores';
import { dashboardApi } from '@/lib/dashboard-api';
import type { ConfidenceTrendResponse, DriftReportsResponse, QAScoresResponse } from '@/lib/dashboard-api';

// ── F-115 Test Data ───────────────────────────────────────────────────

const generateConfidenceData = (): ConfidenceTrendResponse => {
  const daily_trend = [];
  for (let i = 0; i < 30; i++) {
    const date = new Date('2026-03-16');
    date.setDate(date.getDate() + i);
    daily_trend.push({
      date: date.toISOString().split('T')[0],
      avg_confidence: 0.78 + (i / 29) * 0.12,
      min_confidence: 0.55 + (i / 29) * 0.1,
      max_confidence: 0.92 + (i / 29) * 0.05,
      total_predictions: 150 + i * 5,
      low_confidence_count: Math.max(0, 15 - i),
    });
  }
  return {
    daily_trend,
    current_avg: 0.88,
    overall_avg: 0.84,
    trend_direction: 'improving',
    change_vs_previous_period: 0.04,
    distribution: [
      { range: '0-20', count: 12, percentage: 1.2 },
      { range: '20-40', count: 35, percentage: 3.5 },
      { range: '40-60', count: 78, percentage: 7.8 },
      { range: '60-80', count: 340, percentage: 34.0 },
      { range: '80-100', count: 535, percentage: 53.5 },
    ],
    low_confidence_threshold: 0.6,
    critical_threshold: 0.3,
    total_predictions: 8750,
  };
};

// ── F-116 Test Data ───────────────────────────────────────────────────

const mockDriftData: DriftReportsResponse = {
  reports: [
    {
      report_id: 'drift-1',
      detected_at: '2026-04-14T08:00:00Z',
      severity: 'critical',
      metric_name: 'Response Accuracy',
      metric_value: 0.72,
      baseline_value: 0.91,
      drift_pct: -20.9,
      description: 'Response accuracy dropped from 91% to 72% over the past 7 days.',
      status: 'active',
      recovery_action: 'Triggering model retraining with recent data.',
    },
    {
      report_id: 'drift-2',
      detected_at: '2026-04-13T14:00:00Z',
      severity: 'warning',
      metric_name: 'Tone Consistency',
      metric_value: 0.78,
      baseline_value: 0.89,
      drift_pct: -12.4,
      description: 'Tone consistency has degraded slightly.',
      status: 'investigating',
      recovery_action: undefined,
    },
    {
      report_id: 'drift-3',
      detected_at: '2026-04-10T06:00:00Z',
      severity: 'info',
      metric_name: 'Response Latency',
      metric_value: 1.8,
      baseline_value: 1.5,
      drift_pct: 20.0,
      description: 'Average response latency increased by 300ms.',
      status: 'resolved',
      resolved_at: '2026-04-11T10:00:00Z',
      recovery_action: 'Scaling up inference resources.',
    },
  ],
  total: 3,
  active_count: 1,
  last_detected_at: '2026-04-14T08:00:00Z',
  most_severe: 'critical',
};

// ── F-119 Test Data ───────────────────────────────────────────────────

const generateQAScoresData = (): QAScoresResponse => {
  const daily_trend = [];
  for (let i = 0; i < 30; i++) {
    const date = new Date('2026-03-16');
    date.setDate(date.getDate() + i);
    daily_trend.push({
      date: date.toISOString().split('T')[0],
      overall_score: 0.75 + (i / 29) * 0.1,
      accuracy_score: 0.80 + (i / 29) * 0.08,
      completeness_score: 0.72 + (i / 29) * 0.12,
      tone_score: 0.78 + (i / 29) * 0.1,
      relevance_score: 0.82 + (i / 29) * 0.06,
      total_evaluated: 50 + i * 3,
      pass_count: 40 + Math.floor(i * 2.5),
    });
  }
  return {
    daily_trend,
    current_overall: 0.85,
    overall_avg: 0.80,
    pass_rate: 0.87,
    total_evaluated: 1855,
    dimensions: [
      { dimension_name: 'Accuracy', avg_score: 0.88, pass_rate: 0.92, trend: 'improving' },
      { dimension_name: 'Completeness', avg_score: 0.84, pass_rate: 0.88, trend: 'improving' },
      { dimension_name: 'Tone', avg_score: 0.86, pass_rate: 0.90, trend: 'stable' },
      { dimension_name: 'Relevance', avg_score: 0.82, pass_rate: 0.85, trend: 'declining' },
    ],
    trend_direction: 'improving',
    change_vs_previous_period: 0.03,
    threshold_pass: 0.7,
  };
};

// ══════════════════════════════════════════════════════════════════════
// F-115: ConfidenceTrend Tests
// ══════════════════════════════════════════════════════════════════════

describe('ConfidenceTrend Component (F-115)', () => {
  const mockData = generateConfidenceData();

  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<ConfidenceTrend initialData={mockData} />);
      expect(screen.getByText('AI Confidence Trend')).toBeInTheDocument();
    });

    it('renders current confidence percentage', () => {
      render(<ConfidenceTrend initialData={mockData} />);
      expect(screen.getByText('88.0%')).toBeInTheDocument();
    });

    it('renders prediction count', () => {
      const { container } = render(<ConfidenceTrend initialData={mockData} />);
      expect(container.textContent).toContain('8,750 predictions');
    });

    it('renders change vs previous period', () => {
      const { container } = render(<ConfidenceTrend initialData={mockData} />);
      expect(container.textContent).toContain('+4.0% vs prev');
    });

    it('renders distribution section', () => {
      render(<ConfidenceTrend initialData={mockData} />);
      expect(screen.getByText('Confidence Distribution')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role=img with aria-label on chart', () => {
      render(<ConfidenceTrend initialData={mockData} />);
      expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'AI confidence trend chart over 30 days');
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when isLoading is true', () => {
      const { container } = render(<ConfidenceTrend isLoading />);
      expect(screen.queryByText('AI Confidence Trend')).not.toBeInTheDocument();
      expect(container.querySelector('[class*=bg-white]')).toBeTruthy();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no data', () => {
      render(<ConfidenceTrend initialData={{ daily_trend: [], current_avg: 0, overall_avg: 0, trend_direction: 'stable', change_vs_previous_period: 0, distribution: [], low_confidence_threshold: 0.6, critical_threshold: 0.3, total_predictions: 0 }} />);
      expect(screen.getByText('No confidence data')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getConfidenceTrend as jest.Mock).mockResolvedValue(mockData);
      render(<ConfidenceTrend />);
      await waitFor(() => expect(dashboardApi.getConfidenceTrend).toHaveBeenCalledWith(30));
    });

    it('handles API error gracefully', async () => {
      (dashboardApi.getConfidenceTrend as jest.Mock).mockRejectedValue(new Error('Network error'));
      render(<ConfidenceTrend />);
      await waitFor(() => expect(dashboardApi.getConfidenceTrend).toHaveBeenCalled());
      await waitFor(() => expect(screen.getByText('No confidence data')).toBeInTheDocument());
    });
  });

  describe('Edge Cases', () => {
    it('shows negative change vs previous period', () => {
      const declining = { ...mockData, change_vs_previous_period: -0.03 };
      const { container } = render(<ConfidenceTrend initialData={declining} />);
      expect(container.textContent).toContain('-3.0% vs prev');
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// F-116: DriftDetection Tests
// ══════════════════════════════════════════════════════════════════════

describe('DriftDetection Component (F-116)', () => {
  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('Drift Detection')).toBeInTheDocument();
    });

    it('renders all report metrics', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('Response Accuracy')).toBeInTheDocument();
      expect(screen.getByText('Tone Consistency')).toBeInTheDocument();
      expect(screen.getByText('Response Latency')).toBeInTheDocument();
    });

    it('renders severity badges', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('Warning')).toBeInTheDocument();
      expect(screen.getByText('Info')).toBeInTheDocument();
    });

    it('renders status badges', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('active')).toBeInTheDocument();
      expect(screen.getByText('investigating')).toBeInTheDocument();
      expect(screen.getByText('resolved')).toBeInTheDocument();
    });

    it('renders report count', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('3 reports')).toBeInTheDocument();
    });

    it('renders drift descriptions', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText(/accuracy dropped from 91% to 72%/)).toBeInTheDocument();
    });

    it('renders recovery action when present', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('Triggering model retraining with recent data.')).toBeInTheDocument();
    });
  });

  describe('Filter Tabs', () => {
    it('renders filter tabs', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Active (1)')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });

    it('filters to active reports', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      fireEvent.click(screen.getByText('Active (1)'));
      expect(screen.getByText('Response Accuracy')).toBeInTheDocument();
      expect(screen.queryByText('Response Latency')).not.toBeInTheDocument();
    });

    it('filters to resolved reports', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      fireEvent.click(screen.getByText('Resolved'));
      expect(screen.getByText('Response Latency')).toBeInTheDocument();
      expect(screen.queryByText('Response Accuracy')).not.toBeInTheDocument();
    });

    it('shows empty state for filtered view with no matches', () => {
      const onlyResolved = { ...mockDriftData, reports: [mockDriftData.reports[2]], total: 1, active_count: 0 };
      render(<DriftDetection initialData={onlyResolved} />);
      fireEvent.click(screen.getByText('Active (0)'));
      expect(screen.getByText('No active reports')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role=tablist on filter tabs', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'Drift report filter');
    });

    it('has role=tab with aria-selected', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      const tabs = screen.getAllByRole('tab');
      expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
      expect(tabs[1]).toHaveAttribute('aria-selected', 'false');
    });

    it('has role=list on report container', () => {
      render(<DriftDetection initialData={mockDriftData} />);
      expect(screen.getByRole('list')).toHaveAttribute('aria-label', 'Drift reports');
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when isLoading is true', () => {
      const { container } = render(<DriftDetection isLoading />);
      expect(screen.queryByText('Drift Detection')).not.toBeInTheDocument();
      expect(container.querySelector('[class*=bg-white]')).toBeTruthy();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no reports', () => {
      render(<DriftDetection initialData={{ reports: [], total: 0, active_count: 0, last_detected_at: null, most_severe: null }} />);
      expect(screen.getByText('No drift detected')).toBeInTheDocument();
    });

    it('renders header even when empty', () => {
      render(<DriftDetection initialData={{ reports: [], total: 0, active_count: 0, last_detected_at: null, most_severe: null }} />);
      expect(screen.getByText('Drift Detection')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getDriftReports as jest.Mock).mockResolvedValue(mockDriftData);
      render(<DriftDetection />);
      await waitFor(() => expect(dashboardApi.getDriftReports).toHaveBeenCalledWith(20));
    });

    it('handles API error gracefully', async () => {
      (dashboardApi.getDriftReports as jest.Mock).mockRejectedValue(new Error('Server error'));
      render(<DriftDetection />);
      await waitFor(() => expect(dashboardApi.getDriftReports).toHaveBeenCalled());
      await waitFor(() => expect(screen.getByText('No drift detected')).toBeInTheDocument());
    });
  });

  describe('Edge Cases', () => {
    it('shows last detected date', () => {
      const { container } = render(<DriftDetection initialData={mockDriftData} />);
      expect(container.textContent).toContain('Last:');
    });

    it('does not show last detected date when null', () => {
      const noDate = { ...mockDriftData, last_detected_at: null };
      const { container } = render(<DriftDetection initialData={noDate} />);
      expect(container.textContent).not.toContain('Last:');
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// F-119: QAScores Tests
// ══════════════════════════════════════════════════════════════════════

describe('QAScores Component (F-119)', () => {
  const mockData = generateQAScoresData();

  beforeEach(() => jest.clearAllMocks());

  describe('Rendering', () => {
    it('renders header title', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('QA Scores')).toBeInTheDocument();
    });

    it('renders current overall score', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('85.0%')).toBeInTheDocument();
    });

    it('renders evaluated count', () => {
      const { container } = render(<QAScores initialData={mockData} />);
      expect(container.textContent).toContain('1,855 evaluated');
    });

    it('renders pass rate metric card', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('Pass Rate')).toBeInTheDocument();
    });

    it('renders overall avg metric card', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('Overall Avg')).toBeInTheDocument();
    });

    it('renders evaluated metric card', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('Evaluated')).toBeInTheDocument();
    });

    it('renders change vs previous period', () => {
      const { container } = render(<QAScores initialData={mockData} />);
      expect(container.textContent).toContain('+3.0% vs prev');
    });

    it('renders dimension breakdown', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByText('Quality Dimensions')).toBeInTheDocument();
      expect(screen.getByText('Accuracy')).toBeInTheDocument();
      expect(screen.getByText('Completeness')).toBeInTheDocument();
      expect(screen.getByText('Tone')).toBeInTheDocument();
      expect(screen.getByText('Relevance')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role=img with aria-label on chart', () => {
      render(<QAScores initialData={mockData} />);
      expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'QA scores trend chart over 30 days');
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when isLoading is true', () => {
      const { container } = render(<QAScores isLoading />);
      expect(screen.queryByText('QA Scores')).not.toBeInTheDocument();
      expect(container.querySelector('[class*=bg-white]')).toBeTruthy();
    });
  });

  describe('Empty State', () => {
    it('shows empty state with no data', () => {
      render(<QAScores initialData={{ daily_trend: [], current_overall: 0, overall_avg: 0, pass_rate: 0, total_evaluated: 0, dimensions: [], trend_direction: 'stable', change_vs_previous_period: null, threshold_pass: 0.7 }} />);
      expect(screen.getByText('No QA data yet')).toBeInTheDocument();
    });
  });

  describe('API Fetching', () => {
    it('fetches on mount without initialData', async () => {
      (dashboardApi.getQAScores as jest.Mock).mockResolvedValue(mockData);
      render(<QAScores />);
      await waitFor(() => expect(dashboardApi.getQAScores).toHaveBeenCalledWith(30));
    });

    it('handles API error gracefully', async () => {
      (dashboardApi.getQAScores as jest.Mock).mockRejectedValue(new Error('Server error'));
      render(<QAScores />);
      await waitFor(() => expect(dashboardApi.getQAScores).toHaveBeenCalled());
      await waitFor(() => expect(screen.getByText('No QA data yet')).toBeInTheDocument());
    });
  });

  describe('Edge Cases', () => {
    it('hides change vs prev when null', () => {
      const noChange = { ...mockData, change_vs_previous_period: null };
      const { container } = render(<QAScores initialData={noChange} />);
      expect(container.textContent).not.toContain('vs prev');
    });

    it('shows negative change', () => {
      const negativeChange = { ...mockData, change_vs_previous_period: -0.05 };
      const { container } = render(<QAScores initialData={negativeChange} />);
      expect(container.textContent).toContain('-5.0% vs prev');
    });

    it('does not render dimensions when empty', () => {
      const noDims = { ...mockData, dimensions: [] };
      render(<QAScores initialData={noDims} />);
      expect(screen.queryByText('Quality Dimensions')).not.toBeInTheDocument();
    });
  });
});
