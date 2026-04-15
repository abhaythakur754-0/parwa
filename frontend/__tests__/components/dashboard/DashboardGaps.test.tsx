/**
 * Unit Tests: Dashboard A11y Gap Fixes
 *
 * Tests accessibility attributes added to dashboard components:
 * - DashboardAlerts: role="list", aria-label, dismiss all button
 * - SavingsCounter: role="tablist", aria-selected on view switcher
 * - WorkforceAllocation: role="tablist", aria-selected on tab switcher
 * - ActivityFeed: role="tablist", aria-selected on filter tabs
 * - DateRangeSelector: role="tablist", aria-selected on presets
 * - DashboardSidebar: aria-label="Main navigation"
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mocks ──────────────────────────────────────────────────────────────

// Dashboard API mock (used by ActivityFeed)
jest.mock('@/lib/analytics-api', () => ({
  dashboardApi: {
    getHome: jest.fn(),
    getActivityFeed: jest.fn().mockResolvedValue({
      events: [],
      total: 0,
      page: 1,
      page_size: 25,
      has_more: false,
    }),
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

// API mock (used by SavingsCounter & WorkforceAllocation)
jest.mock('@/lib/api', () => ({
  get: jest.fn().mockRejectedValue(new Error('API not available in test')),
}));

// Navigation mock (used by DashboardSidebar)
jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard',
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('next/link', () => {
  return function MockLink({ children, href, ...props }: any) {
    return <a href={href} {...props}>{children}</a>;
  };
});

// Auth mock (used by DashboardSidebar)
jest.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      full_name: 'Test User',
      company_name: 'Test Co',
      email: 'test@test.com',
    },
    logout: jest.fn(),
  }),
}));

// ── Imports ────────────────────────────────────────────────────────────

import DashboardAlerts from '@/components/dashboard/DashboardAlerts';
import SavingsCounter from '@/components/dashboard/SavingsCounter';
import WorkforceAllocation from '@/components/dashboard/WorkforceAllocation';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import DateRangeSelector from '@/components/dashboard/DateRangeSelector';
import DashboardSidebar from '@/components/dashboard/DashboardSidebar';

import type { AnomalyAlert } from '@/types/analytics';

// ── Test Data ──────────────────────────────────────────────────────────

const mockAlerts: AnomalyAlert[] = [
  {
    type: 'volume_spike',
    severity: 'high',
    message: 'Volume spike detected',
    detected_at: new Date(Date.now() - 10000).toISOString(),
  },
  {
    type: 'sla_breach_cluster',
    severity: 'medium',
    message: 'SLA breach cluster',
    detected_at: new Date(Date.now() - 120000).toISOString(),
  },
];

// ════════════════════════════════════════════════════════════════════════
// DashboardAlerts
// ════════════════════════════════════════════════════════════════════════

describe('DashboardAlerts A11y', () => {
  it('has role="list" on container', () => {
    const { container } = render(<DashboardAlerts alerts={mockAlerts} />);
    const list = container.querySelector('[role="list"]');
    expect(list).toBeInTheDocument();
  });

  it('has aria-label="Dashboard alerts" on container', () => {
    const { container } = render(<DashboardAlerts alerts={mockAlerts} />);
    const list = container.querySelector('[role="list"]');
    expect(list).toHaveAttribute('aria-label', 'Dashboard alerts');
  });

  it('renders alert messages', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    expect(screen.getByText('Volume spike detected')).toBeInTheDocument();
    expect(screen.getByText('SLA breach cluster')).toBeInTheDocument();
  });

  it('renders severity badges', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('renders "Dismiss all" button when multiple alerts', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    expect(
      screen.getByRole('button', { name: 'Dismiss all alerts' })
    ).toBeInTheDocument();
  });

  it('has aria-label="Dismiss all alerts" on dismiss all button', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    const dismissAllBtn = screen.getByRole('button', {
      name: 'Dismiss all alerts',
    });
    expect(dismissAllBtn).toHaveAttribute(
      'aria-label',
      'Dismiss all alerts'
    );
  });

  it('dismisses all alerts on "Dismiss all" click', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    const dismissAllBtn = screen.getByRole('button', {
      name: 'Dismiss all alerts',
    });
    fireEvent.click(dismissAllBtn);
    // After dismissing all, no alerts should be visible
    expect(screen.queryByText('Volume spike detected')).not.toBeInTheDocument();
    expect(screen.queryByText('SLA breach cluster')).not.toBeInTheDocument();
  });

  it('renders active alert count', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    expect(screen.getByText('2 active alerts')).toBeInTheDocument();
  });

  it('renders time ago for alerts', () => {
    render(<DashboardAlerts alerts={mockAlerts} />);
    // Both alerts show "Just now" since both are < 5m ago
    const justNow = screen.getAllByText('Just now');
    expect(justNow.length).toBeGreaterThanOrEqual(1);
  });

  it('does not render when alerts array is empty', () => {
    const { container } = render(<DashboardAlerts alerts={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('does not show "Dismiss all" with single alert', () => {
    render(<DashboardAlerts alerts={[mockAlerts[0]]} />);
    expect(
      screen.queryByRole('button', { name: 'Dismiss all alerts' })
    ).not.toBeInTheDocument();
  });

  it('dismisses individual alert on dismiss click', () => {
    const mockOnDismiss = jest.fn();
    render(<DashboardAlerts alerts={mockAlerts} onDismiss={mockOnDismiss} />);
    // Find dismiss buttons (they have title="Dismiss alert")
    const dismissButtons = screen.getAllByTitle('Dismiss alert');
    fireEvent.click(dismissButtons[0]);
    expect(mockOnDismiss).toHaveBeenCalledTimes(1);
  });

  it('applies custom className', () => {
    const { container } = render(
      <DashboardAlerts alerts={mockAlerts} className="custom-gap" />
    );
    const list = container.querySelector('[role="list"]');
    expect(list?.className).toContain('custom-gap');
  });
});

// ════════════════════════════════════════════════════════════════════════
// SavingsCounter
// ════════════════════════════════════════════════════════════════════════

describe('SavingsCounter A11y', () => {
  const mockInitialData = {
    current_month: {
      period: 'Jan 2025',
      date: '2025-01-31',
      tickets_ai: 120,
      tickets_human: 80,
      ai_cost: 36,
      human_cost: 400,
      savings: 364,
      cumulative_savings: 15000,
    },
    previous_month: {
      period: 'Dec 2024',
      date: '2024-12-31',
      tickets_ai: 100,
      tickets_human: 90,
      ai_cost: 30,
      human_cost: 450,
      savings: 420,
      cumulative_savings: 14636,
    },
    all_time_savings: 15000,
    all_time_tickets_ai: 1200,
    all_time_tickets_human: 800,
    monthly_trend: [],
    avg_cost_per_ticket_ai: 0.30,
    avg_cost_per_ticket_human: 5.00,
    savings_pct: 94,
  };

  it('has role="tablist" on view switcher', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    expect(
      screen.getByRole('tablist', { name: 'Savings view' })
    ).toBeInTheDocument();
  });

  it('has aria-label="Savings view" on tablist', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    const tablist = screen.getByRole('tablist', { name: 'Savings view' });
    expect(tablist).toHaveAttribute('aria-label', 'Savings view');
  });

  it('has aria-selected="true" on active tab', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    const overviewTab = screen.getByRole('tab', { name: 'Overview' });
    expect(overviewTab).toHaveAttribute('aria-selected', 'true');
  });

  it('has aria-selected="false" on inactive tab', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    const trendTab = screen.getByRole('tab', { name: 'Trend' });
    expect(trendTab).toHaveAttribute('aria-selected', 'false');
  });

  it('switches aria-selected on tab click', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    const trendTab = screen.getByRole('tab', { name: 'Trend' });
    const overviewTab = screen.getByRole('tab', { name: 'Overview' });

    fireEvent.click(trendTab);
    expect(trendTab).toHaveAttribute('aria-selected', 'true');
    expect(overviewTab).toHaveAttribute('aria-selected', 'false');
  });

  it('renders "AI Savings" header', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    expect(screen.getByText('AI Savings')).toBeInTheDocument();
  });

  it('renders total savings amount', () => {
    render(<SavingsCounter initialData={mockInitialData} />);
    expect(screen.getByText('Total Savings (All Time)')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// WorkforceAllocation
// ════════════════════════════════════════════════════════════════════════

describe('WorkforceAllocation A11y', () => {
  const mockInitialData = {
    current_split: {
      period: 'Jan 2025',
      date: '2025-01-31',
      ai_tickets: 120,
      human_tickets: 80,
      ai_pct: 60,
      human_pct: 40,
      total: 200,
    },
    daily_trend: [],
    by_channel: {},
    by_category: [],
    ai_resolution_rate: 85,
    human_resolution_rate: 72,
  };

  it('has role="tablist" on tab switcher', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    expect(
      screen.getByRole('tablist', { name: 'Workforce view' })
    ).toBeInTheDocument();
  });

  it('has aria-label="Workforce view" on tablist', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    const tablist = screen.getByRole('tablist', { name: 'Workforce view' });
    expect(tablist).toHaveAttribute('aria-label', 'Workforce view');
  });

  it('has aria-selected="true" on active tab (overview)', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    const overviewTab = screen.getByRole('tab', { name: 'overview' });
    expect(overviewTab).toHaveAttribute('aria-selected', 'true');
  });

  it('has aria-selected="false" on inactive tabs', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    const channelsTab = screen.getByRole('tab', { name: 'channels' });
    const categoriesTab = screen.getByRole('tab', { name: 'categories' });
    expect(channelsTab).toHaveAttribute('aria-selected', 'false');
    expect(categoriesTab).toHaveAttribute('aria-selected', 'false');
  });

  it('switches aria-selected on tab click', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    const channelsTab = screen.getByRole('tab', { name: 'channels' });
    const overviewTab = screen.getByRole('tab', { name: 'overview' });

    fireEvent.click(channelsTab);
    expect(channelsTab).toHaveAttribute('aria-selected', 'true');
    expect(overviewTab).toHaveAttribute('aria-selected', 'false');
  });

  it('renders "Workforce Allocation" header', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    expect(screen.getByText('Workforce Allocation')).toBeInTheDocument();
  });

  it('renders all 3 tabs', () => {
    render(<WorkforceAllocation initialData={mockInitialData} />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs.length).toBe(3);
  });
});

// ════════════════════════════════════════════════════════════════════════
// ActivityFeed
// ════════════════════════════════════════════════════════════════════════

describe('ActivityFeed A11y', () => {
  const mockEvents = [
    {
      event_id: 'evt-1',
      event_type: 'ticket_created' as const,
      actor_type: 'customer',
      actor_name: 'John Doe',
      description: 'New ticket created',
      ticket_id: 'ticket-123',
      metadata: {},
      created_at: new Date().toISOString(),
    },
  ];

  it('has role="tablist" on filter tabs container', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    expect(
      screen.getByRole('tablist', { name: 'Activity filter' })
    ).toBeInTheDocument();
  });

  it('has aria-label="Activity filter" on tablist', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    const tablist = screen.getByRole('tablist', { name: 'Activity filter' });
    expect(tablist).toHaveAttribute('aria-label', 'Activity filter');
  });

  it('has aria-selected="true" on active filter tab', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    const allTab = screen.getByRole('tab', { name: 'All' });
    expect(allTab).toHaveAttribute('aria-selected', 'true');
  });

  it('has aria-selected="false" on inactive filter tabs', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    const createdTab = screen.getByRole('tab', { name: 'Created' });
    expect(createdTab).toHaveAttribute('aria-selected', 'false');
  });

  it('switches aria-selected when filter tab is clicked', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    const allTab = screen.getByRole('tab', { name: 'All' });
    const createdTab = screen.getByRole('tab', { name: 'Created' });

    fireEvent.click(createdTab);
    expect(createdTab).toHaveAttribute('aria-selected', 'true');
    expect(allTab).toHaveAttribute('aria-selected', 'false');
  });

  it('renders all 5 filter tabs', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs.length).toBe(5);
  });

  it('hides filter tabs when showFilters is false', () => {
    render(<ActivityFeed initialEvents={mockEvents} showFilters={false} />);
    expect(
      screen.queryByRole('tablist', { name: 'Activity filter' })
    ).not.toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// DateRangeSelector
// ════════════════════════════════════════════════════════════════════════

describe('DateRangeSelector A11y', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('has role="tablist" on container', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('has aria-label="Date range" on tablist', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    expect(screen.getByRole('tablist')).toHaveAttribute(
      'aria-label',
      'Date range'
    );
  });

  it('has aria-selected="true" on active preset', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    const activeTab = screen.getByRole('tab', { name: 'Last 30 Days' });
    expect(activeTab).toHaveAttribute('aria-selected', 'true');
  });

  it('has aria-selected="false" on inactive presets', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    const inactiveTab = screen.getByRole('tab', { name: 'Today' });
    expect(inactiveTab).toHaveAttribute('aria-selected', 'false');
  });

  it('calls onChange when preset is clicked (controlled component)', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    const todayTab = screen.getByRole('tab', { name: 'Today' });

    fireEvent.click(todayTab);
    expect(mockOnChange).toHaveBeenCalledTimes(1);
    // Component is controlled, so aria-selected stays based on value prop
    expect(todayTab).toHaveAttribute('aria-selected', 'false');
  });

  it('reflects aria-selected based on value prop', () => {
    const { rerender } = render(
      <DateRangeSelector value="30d" onChange={mockOnChange} />
    );
    const preset30dTab = screen.getByRole('tab', { name: 'Last 30 Days' });
    expect(preset30dTab).toHaveAttribute('aria-selected', 'true');

    rerender(
      <DateRangeSelector value="today" onChange={mockOnChange} />
    );
    const todayTab = screen.getByRole('tab', { name: 'Today' });
    expect(todayTab).toHaveAttribute('aria-selected', 'true');
    expect(preset30dTab).toHaveAttribute('aria-selected', 'false');
  });

  it('all 4 presets have role="tab"', () => {
    render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs.length).toBe(4);
  });
});

// ════════════════════════════════════════════════════════════════════════
// DashboardSidebar
// ════════════════════════════════════════════════════════════════════════

describe('DashboardSidebar A11y', () => {
  it('has aria-label="Main navigation" on nav element', () => {
    render(<DashboardSidebar collapsed={false} onToggle={jest.fn()} />);
    const nav = screen.getByRole('navigation');
    expect(nav).toHaveAttribute('aria-label', 'Main navigation');
  });

  it('has aria-label="Main navigation" when collapsed', () => {
    render(<DashboardSidebar collapsed={true} onToggle={jest.fn()} />);
    const nav = screen.getByRole('navigation');
    expect(nav).toHaveAttribute('aria-label', 'Main navigation');
  });

  it('toggle button has descriptive aria-label when expanded', () => {
    render(<DashboardSidebar collapsed={false} onToggle={jest.fn()} />);
    expect(
      screen.getByRole('button', { name: 'Collapse sidebar' })
    ).toBeInTheDocument();
  });

  it('toggle button has descriptive aria-label when collapsed', () => {
    render(<DashboardSidebar collapsed={true} onToggle={jest.fn()} />);
    expect(
      screen.getByRole('button', { name: 'Expand sidebar' })
    ).toBeInTheDocument();
  });

  it('nav links are accessible', () => {
    render(<DashboardSidebar collapsed={false} onToggle={jest.fn()} />);
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThanOrEqual(7); // 6 nav + 1 brand + 1 settings
  });
});
