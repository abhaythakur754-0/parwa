/**
 * Day 2 Unit Tests — Overview Page Enhancement + ROI + First Victory
 *
 * Tests for:
 * 1. SystemHealthStrip — shows service health from Socket.io
 * 2. ActiveAgentsSummary — shows agent cards with confidence bars
 * 3. FirstVictoryBanner — celebration banner for first AI resolution
 * 4. RecentApprovals — pending/approved items with action buttons
 * 5. SavingsCounter — animated savings counter with monthly/yearly toggle
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockUseAuth = {
  user: {
    id: 'user-1',
    full_name: 'Test User',
    email: 'test@parwa.ai',
    company_name: 'TestCo',
    company_id: 'tenant-1',
    industry: 'E-commerce',
  },
  logout: jest.fn(),
};

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth,
}));

jest.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
    disconnect: jest.fn(),
    connected: true,
  })),
}));

jest.mock('@/lib/api', () => ({
  get: jest.fn(() => Promise.resolve(null)),
  post: jest.fn(() => Promise.resolve(null)),
  patch: jest.fn(() => Promise.resolve(null)),
  del: jest.fn(() => Promise.resolve(null)),
}));

jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getROIDashboard: jest.fn(() => Promise.resolve({
      current_month: { tickets_ai: 500, tickets_human: 100, ai_cost: 2500, human_cost: 15000, savings: 12500, cumulative_savings: 75000 },
      all_time_savings: 75000,
      all_time_tickets_ai: 6000,
      all_time_tickets_human: 1200,
      savings_pct: 83.3,
      monthly_trend: [],
    })),
    getHome: jest.fn(() => Promise.resolve({
      csat: { overall_avg: 4.2 },
    })),
    getGrowthNudges: jest.fn(() => Promise.resolve({ nudges: [], total: 0, dismissed_count: 0 })),
    getActivityFeed: jest.fn(() => Promise.resolve({ events: [], total: 0, page: 1, page_size: 25, has_more: false })),
    getAdaptationTracker: jest.fn(() => Promise.resolve({ daily_data: [] })),
    getTicketForecast: jest.fn(() => Promise.resolve({ historical: [], forecast: [] })),
    getCSATTrends: jest.fn(() => Promise.resolve({ daily_trend: [], overall_avg: 4.2 })),
    getConfidenceTrend: jest.fn(() => Promise.resolve({ daily_trend: [] })),
    getDriftReports: jest.fn(() => Promise.resolve({ reports: [] })),
    getQAScores: jest.fn(() => Promise.resolve({ daily_trend: [] })),
    getMetrics: jest.fn(() => Promise.resolve({ kpis: [] })),
  },
}));

jest.mock('@/lib/analytics-api', () => ({
  analyticsApi: {
    getDashboard: jest.fn(() => Promise.resolve({
      summary: { total_tickets: 1000, open: 50, in_progress: 30, resolved: 800, closed: 750, critical: 5, high: 20, medium: 100, low: 200, awaiting_client: 40, resolution_rate: 85.5, avg_first_response_time_hours: 1.2, avg_resolution_time_hours: 4.5, auto_resolve_rate: 72 },
      sla: { breached_count: 3, total_tickets_with_sla: 950, compliance_rate: 96.8, approaching_count: 8 },
      trend: [],
      by_category: [],
      date_range: {},
    })),
    getAgents: jest.fn(() => Promise.resolve([])),
    getResponseTime: jest.fn(() => Promise.resolve({ buckets: [] })),
  },
}));

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { success: jest.fn(), error: jest.fn() },
}));

const store: Record<string, string> = {};
const localStorageMock = {
  getItem: jest.fn((key: string) => store[key] || null),
  setItem: jest.fn((key: string, val: string) => { store[key] = val; }),
  removeItem: jest.fn((key: string) => { delete store[key]; }),
  clear: jest.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ── Helper ─────────────────────────────────────────────────────────────

function renderWithSocket(
  ui: React.ReactElement,
  overrides: Record<string, any> = {}
) {
  const { SocketContext } = require('@/lib/socket');
  const defaultCtx = {
    socket: null,
    isConnected: true,
    badgeCounts: { tickets: 0, approvals: 0, notifications: 0 },
    notifications: [],
    latestTicketEvent: null,
    systemStatus: null,
    markNotificationRead: jest.fn(),
    clearNotifications: jest.fn(),
    ...overrides,
  };
  return render(<SocketContext.Provider value={defaultCtx}>{ui}</SocketContext.Provider>);
}

// =====================================================================
// Test 1: SystemHealthStrip
// =====================================================================

describe('SystemHealthStrip', () => {
  it('shows all 7 service indicators', async () => {
    const SystemHealthStrip = require('@/components/dashboard/SystemHealthStrip').default;

    await act(async () => {
      renderWithSocket(<SystemHealthStrip />);
    });

    expect(screen.getByText('LLM')).toBeInTheDocument();
    expect(screen.getByText('Redis')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('SMS')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
    expect(screen.getByText('Voice')).toBeInTheDocument();
  });

  it('shows Live status when connected', async () => {
    const SystemHealthStrip = require('@/components/dashboard/SystemHealthStrip').default;

    await act(async () => {
      renderWithSocket(<SystemHealthStrip />);
    });

    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('shows Reconnecting when disconnected', async () => {
    const SystemHealthStrip = require('@/components/dashboard/SystemHealthStrip').default;

    await act(async () => {
      renderWithSocket(<SystemHealthStrip />, { isConnected: false });
    });

    expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
  });

  it('expands service detail on click', async () => {
    const SystemHealthStrip = require('@/components/dashboard/SystemHealthStrip').default;

    await act(async () => {
      renderWithSocket(<SystemHealthStrip />, {
        systemStatus: {
          status: 'healthy',
          services: {
            llm: { status: 'healthy', latency_ms: 120 },
          },
        },
      });
    });

    const llmBtn = screen.getByText('LLM');
    await act(async () => {
      fireEvent.click(llmBtn);
    });

    // Should show expanded detail
    expect(screen.getByText(/LLM:/)).toBeInTheDocument();
    expect(screen.getByText('120ms response time')).toBeInTheDocument();
  });
});

// =====================================================================
// Test 2: ActiveAgentsSummary
// =====================================================================

describe('ActiveAgentsSummary', () => {
  it('shows loading skeleton', async () => {
    // Override the API mock for this test
    const { get } = require('@/lib/api');
    get.mockImplementationOnce(() => new Promise(() => {})); // Never resolves

    const ActiveAgentsSummary = require('@/components/dashboard/ActiveAgentsSummary').default;

    await act(async () => {
      render(<ActiveAgentsSummary />);
    });

    // Should show the "Active Agents" header even during loading
    // Skeleton loading doesn't show text, just animated divs
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('shows empty state when no agents', async () => {
    const { get } = require('@/lib/api');
    get.mockReset();
    get.mockResolvedValue({ agents: [], total: 0, active: 0, paused: 0, error: 0, tickets_today: 0 });

    const ActiveAgentsSummary = require('@/components/dashboard/ActiveAgentsSummary').default;

    await act(async () => {
      render(<ActiveAgentsSummary />);
    });

    expect(screen.getByText(/No agents configured/)).toBeInTheDocument();
  });

  it('shows agent cards with metrics', async () => {
    const { get } = require('@/lib/api');
    get.mockResolvedValueOnce({
      agents: [
        { agent_id: 'a1', agent_name: 'Support Bot', variant: 'PARWA', status: 'active', confidence: 92, tickets_today: 47, tickets_week: 312, resolution_rate: 89 },
        { agent_id: 'a2', agent_name: 'Billing Agent', variant: 'Mini', status: 'paused', confidence: 78, tickets_today: 0, tickets_week: 45, resolution_rate: 82 },
      ],
      total: 2,
      active: 1,
      paused: 1,
      error: 0,
      tickets_today: 47,
    });

    const ActiveAgentsSummary = require('@/components/dashboard/ActiveAgentsSummary').default;

    await act(async () => {
      render(<ActiveAgentsSummary />);
    });

    expect(screen.getByText('Support Bot')).toBeInTheDocument();
    expect(screen.getByText('Billing Agent')).toBeInTheDocument();
    expect(screen.getByText('1 active')).toBeInTheDocument();
    expect(screen.getByText('47 tickets today')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
    expect(screen.getByText('PARWA')).toBeInTheDocument();
  });
});

// =====================================================================
// Test 3: FirstVictoryBanner
// =====================================================================

describe('FirstVictoryBanner', () => {
  it('does not render when no victory achieved', async () => {
    const { get } = require('@/lib/api');
    get.mockResolvedValueOnce({ achieved: false, dismissed: false });

    const FirstVictoryBanner = require('@/components/dashboard/FirstVictoryBanner').default;

    await act(async () => {
      render(<FirstVictoryBanner />);
    });

    expect(screen.queryByText('First Victory!')).not.toBeInTheDocument();
  });

  it('renders celebration when victory achieved', async () => {
    const { get } = require('@/lib/api');
    get.mockReset();
    get.mockResolvedValue({
      achieved: true,
      ticket_id: 'TK-100',
      ticket_subject: 'Password reset',
      resolution_time_seconds: 47,
      achieved_at: new Date().toISOString(),
      dismissed: false,
    });

    const FirstVictoryBanner = require('@/components/dashboard/FirstVictoryBanner').default;

    await act(async () => {
      render(<FirstVictoryBanner />);
    });

    // Wait for animation delay
    await act(async () => {
      await new Promise(r => setTimeout(r, 700));
    });

    expect(screen.getByText(/First Victory/)).toBeInTheDocument();
    expect(screen.getByText(/47s/)).toBeInTheDocument();
  }, 10000);

  it('can be dismissed', async () => {
    const { get, post } = require('@/lib/api');
    get.mockResolvedValueOnce({
      achieved: true,
      ticket_id: 'TK-100',
      resolution_time_seconds: 30,
      achieved_at: new Date().toISOString(),
      dismissed: false,
    });
    post.mockResolvedValueOnce({});

    const FirstVictoryBanner = require('@/components/dashboard/FirstVictoryBanner').default;

    await act(async () => {
      render(<FirstVictoryBanner />);
    });

    // Wait for animation delay
    await act(async () => {
      await new Promise(r => setTimeout(r, 600));
    });

    const dismissBtn = screen.getByTitle('Dismiss');
    await act(async () => {
      fireEvent.click(dismissBtn);
    });

    // Wait for dismiss animation
    await act(async () => {
      await new Promise(r => setTimeout(r, 400));
    });

    // Banner should no longer be visible
    expect(screen.queryByText('First Victory!')).not.toBeInTheDocument();
  });
});

// =====================================================================
// Test 4: RecentApprovals
// =====================================================================

describe('RecentApprovals', () => {
  it('shows empty state when no approvals', async () => {
    const { get } = require('@/lib/api');
    get.mockResolvedValueOnce({ items: [], total: 0, pending_count: 0 });

    const RecentApprovals = require('@/components/dashboard/RecentApprovals').default;

    await act(async () => {
      render(<RecentApprovals />);
    });

    expect(screen.getByText('No recent approvals')).toBeInTheDocument();
  });

  it('shows approval items with action buttons', async () => {
    const { get } = require('@/lib/api');
    get.mockReset();
    get.mockResolvedValue({
      items: [
        {
          approval_id: 'ap1',
          ticket_id: 'TK-200',
          action_type: 'refund',
          action_description: 'Process refund of $150 for order #12345',
          confidence: 94,
          financial_impact: 150,
          status: 'pending',
          created_at: new Date(Date.now() - 3600000).toISOString(),
        },
        {
          approval_id: 'ap2',
          ticket_id: 'TK-201',
          action_type: 'discount',
          action_description: 'Apply 20% discount for loyal customer',
          confidence: 72,
          financial_impact: 40,
          status: 'approved',
          created_at: new Date(Date.now() - 7200000).toISOString(),
        },
      ],
      total: 2,
      pending_count: 1,
    });

    const RecentApprovals = require('@/components/dashboard/RecentApprovals').default;

    await act(async () => {
      render(<RecentApprovals />);
    });

    expect(screen.getByText('Recent Approvals')).toBeInTheDocument();
    expect(screen.getByText('1 pending')).toBeInTheDocument();
    expect(screen.getByText(/TK-200/)).toBeInTheDocument();
    expect(screen.getByText(/TK-201/)).toBeInTheDocument();
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
    expect(screen.getByText(/View All/)).toBeInTheDocument();
  });
});

// =====================================================================
// Test 5: SavingsCounter
// =====================================================================

describe('SavingsCounter', () => {
  it('shows savings title and monthly/yearly toggle', async () => {
    const SavingsCounter = require('@/components/dashboard/SavingsCounter').default;

    await act(async () => {
      render(<SavingsCounter />);
    });

    expect(screen.getByText("You're Saving")).toBeInTheDocument();
    expect(screen.getByText('Monthly')).toBeInTheDocument();
    expect(screen.getByText('Yearly')).toBeInTheDocument();
  });

  it('shows comparison breakdown', async () => {
    const SavingsCounter = require('@/components/dashboard/SavingsCounter').default;

    await act(async () => {
      render(<SavingsCounter />);
    });

    expect(screen.getByText('PARWA AI')).toBeInTheDocument();
    expect(screen.getByText('Human Agents')).toBeInTheDocument();
    expect(screen.getByText('Savings Rate')).toBeInTheDocument();
  });

  it('switches to yearly view on click', async () => {
    const SavingsCounter = require('@/components/dashboard/SavingsCounter').default;

    await act(async () => {
      render(<SavingsCounter />);
    });

    // Initially monthly
    expect(screen.getByText('Monthly')).toBeInTheDocument();

    const yearlyBtn = screen.getByText('Yearly');
    await act(async () => {
      fireEvent.click(yearlyBtn);
    });

    // Check that yearly context text appears
    expect(screen.getByText(/vs hiring human agents this year/)).toBeInTheDocument();
  });
});
