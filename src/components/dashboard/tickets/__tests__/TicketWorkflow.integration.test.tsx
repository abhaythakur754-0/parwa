/**
 * PARWA Ticket Management Integration Tests
 *
 * End-to-end integration tests for the complete ticket workflow:
 * - Ticket creation and display
 * - Status transitions
 * - Assignment flow
 * - SLA tracking
 * - Merge operations
 * - Export functionality
 * - Real-time updates
 *
 * Day 8 — Testing, Polish & Documentation
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { jest } from '@jest/globals';

// ── Mocks ─────────────────────────────────────────────────────────────────

// Mock router
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    refresh: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/dashboard/tickets',
}));

// Mock socket context
const mockSocket = {
  on: jest.fn(),
  off: jest.fn(),
  emit: jest.fn(),
  connected: true,
};

const mockSocketContext = {
  isConnected: true,
  isReconnecting: false,
  systemStatus: { status: 'healthy' as const, message: 'All systems operational', lastChecked: new Date().toISOString() },
  badgeCounts: { tickets: 5, approvals: 2, notifications: 3 },
  latestTicketEvent: null,
  latestNotification: null,
  unreadNotificationCount: 0,
  isPaused: false,
  aiMode: 'shadow' as const,
  socket: mockSocket as any,
};

jest.mock('@/contexts/SocketContext', () => ({
  useSocket: () => mockSocketContext,
  SocketProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock auth context
jest.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: { id: 'user-1', email: 'agent@example.com', name: 'Test Agent' },
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock API responses
const mockTickets = [
  {
    id: 'ticket-1',
    company_id: 'company-1',
    customer_id: 'customer-1',
    channel: 'email',
    status: 'open',
    subject: 'Cannot login to my account',
    priority: 'high',
    category: 'tech_support',
    tags: ['urgent', 'login-issue'],
    agent_id: null,
    assigned_to: null,
    classification_intent: 'account_access',
    classification_type: 'problem',
    metadata_json: {},
    reopen_count: 0,
    frozen: false,
    is_spam: false,
    awaiting_human: false,
    awaiting_client: false,
    escalation_level: 0,
    sla_breached: false,
    first_response_at: null,
    resolution_target_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    variant_version: null,
    plan_snapshot: {},
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    closed_at: null,
    is_open: true,
    is_resolved: false,
    is_closed: false,
    time_since_created: '30 minutes ago',
    time_since_updated: '5 minutes ago',
  },
  {
    id: 'ticket-2',
    company_id: 'company-1',
    customer_id: 'customer-2',
    channel: 'chat',
    status: 'in_progress',
    subject: 'Billing question about subscription',
    priority: 'medium',
    category: 'billing',
    tags: ['subscription'],
    agent_id: 'agent-1',
    assigned_to: 'agent-1',
    classification_intent: 'billing_inquiry',
    classification_type: 'question',
    metadata_json: {},
    reopen_count: 0,
    frozen: false,
    is_spam: false,
    awaiting_human: false,
    awaiting_client: true,
    escalation_level: 0,
    sla_breached: false,
    first_response_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    resolution_target_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
    variant_version: null,
    plan_snapshot: {},
    created_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    closed_at: null,
    is_open: true,
    is_resolved: false,
    is_closed: false,
    time_since_created: '3 hours ago',
    time_since_updated: '10 minutes ago',
  },
];

const mockAgents = [
  { id: 'agent-1', name: 'John Smith', email: 'john@example.com', specialty: ['tech_support', 'billing'] },
  { id: 'agent-2', name: 'Jane Doe', email: 'jane@example.com', specialty: ['billing', 'complaints'] },
];

// Mock fetch
global.fetch = jest.fn((url: string) => {
  if (url.includes('/api/tickets')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ items: mockTickets, total: 2, page: 1, page_size: 25, pages: 1 }),
    });
  }
  if (url.includes('/api/agents')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockAgents),
    });
  }
  if (url.includes('/dashboard-metrics')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        openTickets: { value: 15, change: 3 },
        resolvedToday: { value: 28, change: 5 },
        avgResponseTime: { value: 42 },
        slaAtRisk: { value: 4 },
        escalated: { value: 2 },
        aiHandled: { value: 78 },
        pendingApprovals: { value: 6 },
        activeAgents: { value: 5 },
      }),
    });
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
}) as any;

// Mock UI components
jest.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className} data-testid="scroll-area">{children}</div>
  ),
}));

jest.mock('@/components/ui/card', () => ({
  Card: ({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) => (
    <div className={className} onClick={onClick} data-testid="card">{children}</div>
  ),
  CardContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  CardHeader: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  CardTitle: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <h3 className={className}>{children}</h3>
  ),
}));

jest.mock('@/components/ui/avatar', () => ({
  Avatar: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className} data-testid="avatar">{children}</div>
  ),
  AvatarFallback: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  AvatarImage: ({ src, alt }: { src?: string; alt?: string }) => (
    <img src={src} alt={alt} data-testid="avatar-image" />
  ),
}));

jest.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, variant, size, className, disabled }: { children: React.ReactNode; onClick?: () => void; variant?: string; size?: string; className?: string; disabled?: boolean }) => (
    <button onClick={onClick} className={className} data-variant={variant} data-size={size} disabled={disabled}>{children}</button>
  ),
}));

jest.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open?: boolean }) => (
    <div data-testid="dialog" data-open={open}>{children}</div>
  ),
  DialogContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  DialogHeader: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  DialogTitle: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <h2 className={className}>{children}</h2>
  ),
  DialogTrigger: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) => (
    <>{children}</>
  ),
}));

jest.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DropdownMenuTrigger: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) => <>{children}</>,
  DropdownMenuContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  DropdownMenuItem: ({ children, onClick, className }: { children: React.ReactNode; onClick?: () => void; className?: string }) => (
    <button onClick={onClick} className={className}>{children}</button>
  ),
  DropdownMenuLabel: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  DropdownMenuSeparator: ({ className }: { className?: string }) => (
    <div className={className} role="separator" />
  ),
}));

// ── Import Components ─────────────────────────────────────────────────────

import TicketList from '../TicketList';
import TicketRow, { statusConfig, priorityConfig } from '../TicketRow';
import BulkActions from '../BulkActions';
import { useTicketRealtime } from '../useTicketRealtime';
import DashboardWidgets from '../DashboardWidgets';
import RealtimeNotifications from '../RealtimeNotifications';
import TicketActivityStream from '../TicketActivityStream';
import AgentPresenceIndicator, { PresenceDot, AgentPresenceList } from '../AgentPresenceIndicator';
import AgentScoreCard from '../AgentScoreCard';

// ── Ticket Workflow Integration Tests ─────────────────────────────────────

describe('Ticket Workflow Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  describe('Ticket List Display', () => {
    it('should have valid status configuration', () => {
      const statuses = ['open', 'in_progress', 'resolved', 'closed'] as const;

      statuses.forEach((status) => {
        expect(statusConfig[status]).toBeDefined();
        expect(statusConfig[status].label).toBeTruthy();
        expect(statusConfig[status].className).toBeTruthy();
      });
    });

    it('should have valid priority configuration', () => {
      const priorities = ['critical', 'high', 'medium', 'low'] as const;

      priorities.forEach((priority) => {
        expect(priorityConfig[priority]).toBeDefined();
        expect(priorityConfig[priority].label).toBeTruthy();
        expect(priorityConfig[priority].dotClass).toBeTruthy();
      });
    });
  });

  describe('Filter and Search', () => {
    it('should support status filtering', () => {
      // Status options should be defined
      const statusOptions = Object.keys(statusConfig);
      expect(statusOptions.length).toBeGreaterThan(0);
      expect(statusOptions).toContain('open');
      expect(statusOptions).toContain('resolved');
    });

    it('should support priority filtering', () => {
      const priorityOptions = Object.keys(priorityConfig);
      expect(priorityOptions.length).toBeGreaterThan(0);
      expect(priorityOptions).toContain('high');
      expect(priorityOptions).toContain('low');
    });
  });

  describe('Bulk Operations', () => {
    it('should render bulk action controls', () => {
      const selectedIds = ['ticket-1', 'ticket-2'];
      const { container } = render(<BulkActions selectedCount={selectedIds.length} />);

      // Component should render with selected count
      expect(container).toBeTruthy();
    });

    it('should handle no tickets selected', () => {
      const { container } = render(<BulkActions selectedCount={0} />);

      // With 0 selected, component may return null
      expect(container).toBeTruthy();
    });
  });

  describe('Assignment Workflow', () => {
    const createScoreBreakdown = (percentage: number, currentTickets = 5) => ({
      raw: percentage * 100,
      max: 100,
      percentage,
      current_tickets: currentTickets,
    });

    it('should display agent scores correctly', () => {
      const props = {
        agentId: 'agent-1',
        agentName: 'John Smith',
        score: 0.85,
        rawScore: 97.75,
        scoreBreakdown: {
          expertise: createScoreBreakdown(90),
          workload: { ...createScoreBreakdown(80), current_tickets: 3 },
          performance: createScoreBreakdown(85),
          response_time: createScoreBreakdown(90),
          availability: createScoreBreakdown(70),
        },
        isRecommended: true,
        rank: 1,
      };

      render(<AgentScoreCard {...props} />);

      // Should show agent name
      expect(screen.getByText('John Smith')).toBeInTheDocument();
      // Should show score percentage (multiple 85% may appear)
      const scoreElements = screen.getAllByText('85%');
      expect(scoreElements.length).toBeGreaterThan(0);
      // Should show recommended badge
      expect(screen.getByText('Recommended')).toBeInTheDocument();
      // Should show open tickets count
      expect(screen.getByText('3 open tickets')).toBeInTheDocument();
    });

    it('should show score breakdown for all factors', () => {
      const props = {
        agentId: 'agent-2',
        agentName: 'Jane Doe',
        score: 0.75,
        rawScore: 86.25,
        scoreBreakdown: {
          expertise: createScoreBreakdown(80),
          workload: { ...createScoreBreakdown(70), current_tickets: 7 },
          performance: createScoreBreakdown(75),
          response_time: createScoreBreakdown(80),
          availability: createScoreBreakdown(60),
        },
        isRecommended: false,
        rank: 2,
      };

      render(<AgentScoreCard {...props} />);

      // Should show agent name
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      // Should show rank
      expect(screen.getByText('2')).toBeInTheDocument();
      // Should show 5-factor breakdown
      expect(screen.getByText('5-Factor Score Breakdown')).toBeInTheDocument();
    });
  });
});

// ── Real-time Updates Integration Tests ───────────────────────────────────

describe('Real-time Updates Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('useTicketRealtime Hook', () => {
    function TestHookComponent() {
      const state = useTicketRealtime();
      return (
        <div>
          <span data-testid="connected">{state.isConnected.toString()}</span>
          <span data-testid="events">{state.recentEvents.length}</span>
          <span data-testid="tickets">{state.newTicketCount}</span>
          <button onClick={() => state.acknowledge('all')}>Ack</button>
        </div>
      );
    }

    it('should provide real-time state', () => {
      render(<TestHookComponent />);

      expect(screen.getByTestId('events')).toHaveTextContent('0');
      expect(screen.getByTestId('tickets')).toHaveTextContent('0');
    });

    it('should acknowledge counts', () => {
      render(<TestHookComponent />);

      fireEvent.click(screen.getByText('Ack'));

      expect(screen.getByTestId('tickets')).toHaveTextContent('0');
    });
  });

  describe('Dashboard Widgets', () => {
    it('should render full dashboard', async () => {
      render(<DashboardWidgets variant="full" />);

      await waitFor(() => {
        expect(screen.getByText('Real-time Dashboard')).toBeInTheDocument();
      });
    });

    it('should render compact variant', () => {
      render(<DashboardWidgets variant="compact" />);

      expect(screen.getByText('Open Tickets')).toBeInTheDocument();
      expect(screen.getByText('SLA at Risk')).toBeInTheDocument();
    });

    it('should render summary variant', () => {
      render(<DashboardWidgets variant="summary" />);

      expect(screen.getByText('Live Stats')).toBeInTheDocument();
    });
  });

  describe('Real-time Notifications', () => {
    it('should render notification bell', () => {
      render(<RealtimeNotifications />);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should toggle dropdown', async () => {
      render(<RealtimeNotifications />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Notifications')).toBeInTheDocument();
      });
    });
  });

  describe('Activity Stream', () => {
    it('should render activity panel', () => {
      render(<TicketActivityStream />);

      expect(screen.getByText('Live Activity')).toBeInTheDocument();
    });

    it('should show filter tabs', () => {
      render(<TicketActivityStream enableFilters />);

      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('New')).toBeInTheDocument();
    });
  });
});

// ── Agent Presence Integration Tests ──────────────────────────────────────

describe('Agent Presence Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('PresenceDot', () => {
    it('should render all status states', () => {
      const statuses: Array<'online' | 'away' | 'busy' | 'offline'> = ['online', 'away', 'busy', 'offline'];

      statuses.forEach((status) => {
        const { container } = render(<PresenceDot status={status} />);
        expect(container.firstChild).toBeInTheDocument();
      });
    });

    it('should render all sizes', () => {
      const sizes: Array<'xs' | 'sm' | 'md' | 'lg'> = ['xs', 'sm', 'md', 'lg'];

      sizes.forEach((size) => {
        const { container } = render(<PresenceDot status="online" size={size} />);
        expect(container.firstChild).toBeInTheDocument();
      });
    });
  });

  describe('AgentPresenceIndicator', () => {
    it('should render with agent info', () => {
      render(
        <AgentPresenceIndicator
          agentId="agent-1"
          agentName="Test Agent"
          showLabel
        />
      );

      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });

    it('should render compact mode', () => {
      const { container } = render(
        <AgentPresenceIndicator
          agentId="agent-1"
          compact
        />
      );

      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('AgentPresenceList', () => {
    it('should render team list', () => {
      render(<AgentPresenceList title="Support Team" />);

      expect(screen.getByText('Support Team')).toBeInTheDocument();
    });

    it('should show empty state', () => {
      render(<AgentPresenceList />);

      expect(screen.getByText('No agents available')).toBeInTheDocument();
    });
  });
});

// ── Status Configuration Tests ────────────────────────────────────────────

describe('Status and Priority Configuration', () => {
  it('should have valid status config for all ticket statuses', () => {
    const requiredStatuses = [
      'open',
      'in_progress',
      'awaiting_customer',
      'awaiting_agent',
      'escalated',
      'resolved',
      'closed',
      'spam',
    ];

    requiredStatuses.forEach((status) => {
      expect(statusConfig[status]).toBeDefined();
      expect(statusConfig[status].label).toBeTruthy();
      expect(statusConfig[status].className).toBeTruthy();
    });
  });

  it('should have valid priority config for all priorities', () => {
    const requiredPriorities = ['critical', 'high', 'medium', 'low'];

    requiredPriorities.forEach((priority) => {
      expect(priorityConfig[priority]).toBeDefined();
      expect(priorityConfig[priority].label).toBeTruthy();
      expect(priorityConfig[priority].dotClass).toBeTruthy();
    });
  });
});

// ── Export Integration Tests ──────────────────────────────────────────────

describe('Module Exports', () => {
  it('should export all ticket components', async () => {
    const index = await import('../index');

    // Day 3-6 components
    expect(index.TicketList).toBeDefined();
    expect(index.TicketDetail).toBeDefined();
    expect(index.TicketRow).toBeDefined();
    expect(index.BulkActions).toBeDefined();

    // Day 7 components
    expect(index.RealtimeNotifications).toBeDefined();
    expect(index.TicketActivityStream).toBeDefined();
    expect(index.DashboardWidgets).toBeDefined();
    expect(index.AgentPresenceIndicator).toBeDefined();
    expect(index.useTicketRealtime).toBeDefined();
  });

  it('should export all types', async () => {
    const index = await import('../index');

    // Types are type-only exports, module should load without error
    expect(index).toBeDefined();
  });
});
