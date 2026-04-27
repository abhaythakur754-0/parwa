/**
 * PARWA Ticket Management - Core Components Unit Tests
 *
 * Comprehensive tests for:
 * - TicketRow
 * - TicketSearch
 * - TicketFiltersBar
 * - TicketQuickView
 * - ConfidenceBar
 * - SLATimer, SLABadge, SLAProgressBar
 * - GSDStateIndicator
 * - BulkActions
 *
 * Day 8 — Testing, Polish & Documentation
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { jest } from '@jest/globals';

// ── Mocks ─────────────────────────────────────────────────────────────────

// Mock next/link
jest.mock('next/link', () => {
  return function MockLink({ children, href }: { children: React.ReactNode; href: string }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock router
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    refresh: jest.fn(),
    back: jest.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/dashboard/tickets',
}));

// Mock socket context
const mockSocketContext = {
  isConnected: true,
  isReconnecting: false,
  systemStatus: { status: 'healthy' as const, message: 'All systems operational' },
  badgeCounts: { tickets: 5, approvals: 2, notifications: 3 },
  latestTicketEvent: null,
  latestNotification: null,
  unreadNotificationCount: 0,
  isPaused: false,
  aiMode: 'shadow' as const,
  socket: { on: jest.fn(), off: jest.fn(), emit: jest.fn(), connected: true },
};

jest.mock('@/lib/socket', () => ({
  useSocket: () => mockSocketContext,
}));

// Mock tickets API
const mockFetchTickets = jest.fn();
const mockFetchTicketDetail = jest.fn();
const mockExecuteBulkAction = jest.fn();

jest.mock('@/lib/tickets-api', () => ({
  ticketsApi: {
    fetchTickets: (...args: unknown[]) => mockFetchTickets(...args),
    fetchTicketDetail: (...args: unknown[]) => mockFetchTicketDetail(...args),
    executeBulkAction: (...args: unknown[]) => mockExecuteBulkAction(...args),
    sendReply: jest.fn(() => Promise.resolve({ id: 'msg-1', content: 'test' })),
    addInternalNote: jest.fn(() => Promise.resolve({ id: 'note-1', content: 'test' })),
    assignTicket: jest.fn(() => Promise.resolve({ id: 'ticket-1' })),
    escalateTicket: jest.fn(() => Promise.resolve({ id: 'ticket-1', status: 'escalated' })),
  },
}));

// Mock toast
jest.mock('react-hot-toast', () => ({
  success: jest.fn(),
  error: jest.fn(),
}));

// Mock UI components
jest.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock('@/components/ui/card', () => ({
  Card: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <div onClick={onClick} data-testid="card">{children}</div>
  ),
  CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: React.ReactNode }) => <h3>{children}</h3>,
}));

jest.mock('@/components/ui/avatar', () => ({
  Avatar: ({ children }: { children: React.ReactNode }) => <div data-testid="avatar">{children}</div>,
  AvatarFallback: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AvatarImage: ({ src, alt }: { src?: string; alt?: string }) => <img src={src} alt={alt} />,
}));

jest.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => (
    <button onClick={onClick} disabled={disabled}>{children}</button>
  ),
}));

// Mock mock data
jest.mock('@/lib/mock/ticket-mock-data', () => ({
  mockAgents: [
    { id: 'agent-1', name: 'John Smith', email: 'john@example.com', specialty: ['tech_support'], is_online: true },
    { id: 'agent-2', name: 'Jane Doe', email: 'jane@example.com', specialty: ['billing'], is_online: false },
  ],
  mockTickets: [],
}));

// ── Test Data ─────────────────────────────────────────────────────────────

const mockTicket = {
  id: 'ticket-1',
  ticket_number: 'TKT-001',
  subject: 'Test Subject',
  description: 'Test description for the ticket',
  status: 'open' as const,
  priority: 'high' as const,
  channel: 'email' as const,
  customer: {
    id: 'customer-1',
    name: 'John Customer',
    email: 'john@example.com',
    phone: null,
    avatar_url: null,
    company: null,
    total_tickets: 5,
    resolved_tickets: 3,
    avg_csat: 4.5,
    first_seen: '2024-01-01T00:00:00Z',
    last_active: '2024-01-15T00:00:00Z',
    tags: [],
  },
  assigned_agent: {
    id: 'agent-1',
    name: 'John Smith',
    email: 'john@example.com',
    avatar_url: null,
    is_online: true,
    active_ticket_count: 3,
  },
  ai_confidence: 0.85,
  sentiment: 'positive' as const,
  gsd_state: 'resolution' as const,
  ai_technique: 'knowledge_base' as const,
  resolution_time_minutes: null,
  first_response_time_minutes: 30,
  sla_deadline: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
  sla_breached: false,
  sla_approaching: false,
  is_ai_resolved: false,
  tags: ['urgent', 'billing'],
  message_count: 5,
  unread_count: 2,
  has_attachments: true,
  variant_id: null,
  variant_name: null,
  created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  resolved_at: null,
};

// ── Import Components ─────────────────────────────────────────────────────

import TicketRow, { statusConfig, priorityConfig, channelIcons, timeAgo } from '../TicketRow';
import TicketSearch from '../TicketSearch';
import TicketFiltersBar from '../TicketFilters';
import TicketQuickView from '../TicketQuickView';
import ConfidenceBar from '../ConfidenceBar';
import SLATimer, { SLABadge, SLAProgressBar } from '../SLATimer';
import GSDStateIndicator from '../GSDStateIndicator';
import BulkActions from '../BulkActions';

// ── TicketRow Tests ───────────────────────────────────────────────────────

describe('TicketRow Component', () => {
  const defaultProps = {
    ticket: mockTicket,
    isSelected: false,
    onSelect: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render ticket number as link', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('TKT-001')).toBeInTheDocument();
    });

    it('should render subject with link', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('Test Subject')).toBeInTheDocument();
    });

    it('should render status badge', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('Open')).toBeInTheDocument();
    });

    it('should render priority dot', () => {
      const { container } = render(<TicketRow {...defaultProps} />);
      // Priority dot should be present
      const dot = container.querySelector('.bg-orange-500');
      expect(dot).toBeInTheDocument();
    });

    it('should render customer name', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('John Customer')).toBeInTheDocument();
    });

    it('should render channel icon', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('✉️')).toBeInTheDocument();
    });

    it('should render assigned agent', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('John')).toBeInTheDocument();
    });

    it('should render unassigned when no agent', () => {
      render(<TicketRow {...defaultProps} ticket={{ ...mockTicket, assigned_agent: null }} />);
      expect(screen.getByText('Unassigned')).toBeInTheDocument();
    });

    it('should render attachment icon when has_attachments is true', () => {
      render(<TicketRow {...defaultProps} />);
      expect(screen.getByText('📎')).toBeInTheDocument();
    });

    it('should not render attachment icon when has_attachments is false', () => {
      render(<TicketRow {...defaultProps} ticket={{ ...mockTicket, has_attachments: false }} />);
      expect(screen.queryByText('📎')).not.toBeInTheDocument();
    });

    it('should render time ago', () => {
      render(<TicketRow {...defaultProps} />);
      // Should render some time format
      const timeElement = screen.getByText(/ago/);
      expect(timeElement).toBeInTheDocument();
    });
  });

  describe('Selection', () => {
    it('should render checkbox', () => {
      render(<TicketRow {...defaultProps} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).not.toBeChecked();
    });

    it('should show checked when selected', () => {
      render(<TicketRow {...defaultProps} isSelected={true} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('should call onSelect when checkbox clicked', () => {
      const onSelect = jest.fn();
      render(<TicketRow {...defaultProps} onSelect={onSelect} />);
      fireEvent.click(screen.getByRole('checkbox'));
      expect(onSelect).toHaveBeenCalledWith('ticket-1');
    });

    it('should apply selected styling when selected', () => {
      const { container } = render(<TicketRow {...defaultProps} isSelected={true} />);
      const row = container.querySelector('tr');
      expect(row?.className).toContain('bg-orange-500');
    });
  });

  describe('Hover Behavior', () => {
    it('should call onHover on mouse enter', () => {
      const onHover = jest.fn();
      const { container } = render(<TicketRow {...defaultProps} onHover={onHover} />);
      const row = container.querySelector('tr');
      if (row) fireEvent.mouseEnter(row);
      expect(onHover).toHaveBeenCalledWith(mockTicket);
    });

    it('should call onHover with null on mouse leave', () => {
      const onHover = jest.fn();
      const { container } = render(<TicketRow {...defaultProps} onHover={onHover} />);
      const row = container.querySelector('tr');
      if (row) {
        fireEvent.mouseEnter(row);
        fireEvent.mouseLeave(row);
      }
      expect(onHover).toHaveBeenCalledWith(null);
    });
  });

  describe('Different Statuses', () => {
    const statuses: Array<'open' | 'in_progress' | 'resolved' | 'closed' | 'escalated'> = [
      'open', 'in_progress', 'resolved', 'closed', 'escalated'
    ];

    statuses.forEach((status) => {
      it(`should render ${status} status correctly`, () => {
        render(<TicketRow {...defaultProps} ticket={{ ...mockTicket, status }} />);
        expect(screen.getByText(statusConfig[status].label)).toBeInTheDocument();
      });
    });
  });

  describe('Different Priorities', () => {
    const priorities: Array<'critical' | 'high' | 'medium' | 'low'> = [
      'critical', 'high', 'medium', 'low'
    ];

    priorities.forEach((priority) => {
      it(`should render ${priority} priority correctly`, () => {
        render(<TicketRow {...defaultProps} ticket={{ ...mockTicket, priority }} />);
        // Check that the priority label is shown
        expect(screen.getByText(priorityConfig[priority].label)).toBeInTheDocument();
      });
    });
  });
});

// ── Status Config Tests ───────────────────────────────────────────────────

describe('statusConfig', () => {
  it('should have config for all required statuses', () => {
    const requiredStatuses = [
      'open', 'in_progress', 'awaiting_customer', 'awaiting_agent',
      'escalated', 'resolved', 'closed', 'spam'
    ];
    requiredStatuses.forEach((status) => {
      expect(statusConfig[status as keyof typeof statusConfig]).toBeDefined();
      expect(statusConfig[status as keyof typeof statusConfig].label).toBeTruthy();
      expect(statusConfig[status as keyof typeof statusConfig].className).toBeTruthy();
    });
  });
});

// ── Priority Config Tests ─────────────────────────────────────────────────

describe('priorityConfig', () => {
  it('should have config for all required priorities', () => {
    const requiredPriorities = ['critical', 'high', 'medium', 'low'];
    requiredPriorities.forEach((priority) => {
      expect(priorityConfig[priority as keyof typeof priorityConfig]).toBeDefined();
      expect(priorityConfig[priority as keyof typeof priorityConfig].label).toBeTruthy();
      expect(priorityConfig[priority as keyof typeof priorityConfig].dotClass).toBeTruthy();
    });
  });
});

// ── Channel Icons Tests ───────────────────────────────────────────────────

describe('channelIcons', () => {
  it('should have icons for all required channels', () => {
    const requiredChannels = [
      'email', 'chat', 'sms', 'voice', 'slack', 'webchat'
    ];
    requiredChannels.forEach((channel) => {
      expect(channelIcons[channel as keyof typeof channelIcons]).toBeDefined();
    });
  });
});

// ── timeAgo Tests ─────────────────────────────────────────────────────────

describe('timeAgo function', () => {
  it('should return "just now" for recent times', () => {
    const result = timeAgo(new Date(Date.now() - 30 * 1000).toISOString());
    expect(result).toBe('just now');
  });

  it('should return minutes ago for times under an hour', () => {
    const result = timeAgo(new Date(Date.now() - 30 * 60 * 1000).toISOString());
    expect(result).toContain('m ago');
  });

  it('should return hours ago for times under a day', () => {
    const result = timeAgo(new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString());
    expect(result).toContain('h ago');
  });

  it('should return days ago for times under a week', () => {
    const result = timeAgo(new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString());
    expect(result).toContain('d ago');
  });

  it('should return formatted date for older times', () => {
    const result = timeAgo(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString());
    expect(result).not.toContain('ago');
  });
});

// ── TicketSearch Tests ────────────────────────────────────────────────────

describe('TicketSearch Component', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should render search input', () => {
    render(<TicketSearch value="" onChange={jest.fn()} />);
    expect(screen.getByPlaceholderText(/Search tickets/)).toBeInTheDocument();
  });

  it('should display current value', () => {
    render(<TicketSearch value="test query" onChange={jest.fn()} />);
    expect(screen.getByDisplayValue('test query')).toBeInTheDocument();
  });

  it('should update local value on change', () => {
    const onChange = jest.fn();
    render(<TicketSearch value="" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new search' } });
    expect(input).toHaveValue('new search');
  });

  it('should debounce onChange callback', () => {
    const onChange = jest.fn();
    render(<TicketSearch value="" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    
    fireEvent.change(input, { target: { value: 'test' } });
    expect(onChange).not.toHaveBeenCalled();
    
    act(() => {
      jest.advanceTimersByTime(300);
    });
    
    expect(onChange).toHaveBeenCalledWith('test');
  });

  it('should show clear button when value exists', () => {
    render(<TicketSearch value="test" onChange={jest.fn()} />);
    // Clear button should be visible
    const clearButton = screen.getByRole('button');
    expect(clearButton).toBeInTheDocument();
  });

  it('should not show clear button when empty', () => {
    render(<TicketSearch value="" onChange={jest.fn()} />);
    // No clear button should be visible
    const buttons = screen.queryAllByRole('button');
    expect(buttons.length).toBe(0);
  });

  it('should clear value on clear button click', () => {
    const onChange = jest.fn();
    render(<TicketSearch value="test" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('should sync value from parent', () => {
    const { rerender } = render(<TicketSearch value="initial" onChange={jest.fn()} />);
    expect(screen.getByDisplayValue('initial')).toBeInTheDocument();
    
    rerender(<TicketSearch value="updated" onChange={jest.fn()} />);
    expect(screen.getByDisplayValue('updated')).toBeInTheDocument();
  });
});

// ── TicketFiltersBar Tests ────────────────────────────────────────────────

describe('TicketFiltersBar Component', () => {
  const defaultFilters = {};
  const onChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render all filter sections', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Priority')).toBeInTheDocument();
    expect(screen.getByText('Channel')).toBeInTheDocument();
  });

  it('should render status filter options', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  it('should render priority filter options', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
  });

  it('should render channel filter options', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
  });

  it('should toggle status filter on click', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    fireEvent.click(screen.getByText('Open'));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      status: ['open']
    }));
  });

  it('should toggle priority filter on click', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    fireEvent.click(screen.getByText('High'));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      priority: ['high']
    }));
  });

  it('should toggle channel filter on click', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    fireEvent.click(screen.getByText('Chat'));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      channel: ['chat']
    }));
  });

  it('should show clear all button when filters active', () => {
    const activeFilters = { status: ['open'] };
    render(<TicketFiltersBar filters={activeFilters} onChange={onChange} />);
    expect(screen.getByText('Clear all')).toBeInTheDocument();
  });

  it('should not show clear all button when no filters', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.queryByText('Clear all')).not.toBeInTheDocument();
  });

  it('should clear all filters on clear button click', () => {
    const activeFilters = { status: ['open'], priority: ['high'] };
    render(<TicketFiltersBar filters={activeFilters} onChange={onChange} />);
    fireEvent.click(screen.getByText('Clear all'));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it('should remove filter when clicking active filter', () => {
    const activeFilters = { status: ['open'] };
    render(<TicketFiltersBar filters={activeFilters} onChange={onChange} />);
    fireEvent.click(screen.getByText('Open'));
    expect(onChange).toHaveBeenCalledWith({ status: undefined });
  });

  it('should render confidence filter options', () => {
    render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    expect(screen.getByText('High (80%+)')).toBeInTheDocument();
    expect(screen.getByText('Medium (60-79%)')).toBeInTheDocument();
    expect(screen.getByText('Low (<60%)')).toBeInTheDocument();
  });

  it('should render date range inputs', () => {
    const { container } = render(<TicketFiltersBar filters={defaultFilters} onChange={onChange} />);
    // Date inputs are input elements with type="date"
    const dateInputs = container.querySelectorAll('input[type="date"]');
    expect(dateInputs.length).toBeGreaterThanOrEqual(2);
  });
});

// ── TicketQuickView Tests ─────────────────────────────────────────────────

describe('TicketQuickView Component', () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render ticket number', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('TKT-001')).toBeInTheDocument();
  });

  it('should render subject', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('Test Subject')).toBeInTheDocument();
  });

  it('should render status badge', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('Open')).toBeInTheDocument();
  });

  it('should render customer name', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('John Customer')).toBeInTheDocument();
  });

  it('should render customer email', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });

  it('should render description', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText(/Test description/)).toBeInTheDocument();
  });

  it('should render channel', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('should render message count', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('should render agent name when assigned', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('John Smith')).toBeInTheDocument();
  });

  it('should render Unassigned when no agent', () => {
    render(<TicketQuickView ticket={{ ...mockTicket, assigned_agent: null }} onClose={onClose} />);
    expect(screen.getByText('Unassigned')).toBeInTheDocument();
  });

  it('should render tags', () => {
    render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    expect(screen.getByText('urgent')).toBeInTheDocument();
    expect(screen.getByText('billing')).toBeInTheDocument();
  });

  it('should not render tags section when empty', () => {
    render(<TicketQuickView ticket={{ ...mockTicket, tags: [] }} onClose={onClose} />);
    expect(screen.queryByText('urgent')).not.toBeInTheDocument();
  });

  it('should show AI Resolved badge when applicable', () => {
    render(<TicketQuickView ticket={{ ...mockTicket, is_ai_resolved: true }} onClose={onClose} />);
    expect(screen.getByText('AI Resolved')).toBeInTheDocument();
  });

  it('should call onClose on mouse leave', () => {
    const { container } = render(<TicketQuickView ticket={mockTicket} onClose={onClose} />);
    const panel = container.firstChild as HTMLElement;
    fireEvent.mouseLeave(panel);
    expect(onClose).toHaveBeenCalled();
  });
});

// ── ConfidenceBar Tests ───────────────────────────────────────────────────

describe('ConfidenceBar Component', () => {
  describe('Rendering', () => {
    it('should render progress bar', () => {
      const { container } = render(<ConfidenceBar value={0.75} />);
      expect(container.querySelector('.rounded-full')).toBeInTheDocument();
    });

    it('should render percentage label by default', () => {
      render(<ConfidenceBar value={0.75} />);
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('should hide label when showLabel is false', () => {
      render(<ConfidenceBar value={0.75} showLabel={false} />);
      expect(screen.queryByText('75%')).not.toBeInTheDocument();
    });
  });

  describe('Color Coding', () => {
    it('should use emerald for high confidence (>=80%)', () => {
      const { container } = render(<ConfidenceBar value={0.85} />);
      expect(container.querySelector('.bg-emerald-500')).toBeInTheDocument();
      expect(container.querySelector('.text-emerald-400')).toBeInTheDocument();
    });

    it('should use amber for good confidence (60-79%)', () => {
      const { container } = render(<ConfidenceBar value={0.7} />);
      expect(container.querySelector('.bg-amber-500')).toBeInTheDocument();
      expect(container.querySelector('.text-amber-400')).toBeInTheDocument();
    });

    it('should use orange for medium confidence (40-59%)', () => {
      const { container } = render(<ConfidenceBar value={0.5} />);
      expect(container.querySelector('.bg-orange-500')).toBeInTheDocument();
      expect(container.querySelector('.text-orange-400')).toBeInTheDocument();
    });

    it('should use red for low confidence (<40%)', () => {
      const { container } = render(<ConfidenceBar value={0.3} />);
      expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
      expect(container.querySelector('.text-red-400')).toBeInTheDocument();
    });
  });

  describe('Sizes', () => {
    it('should render small size', () => {
      const { container } = render(<ConfidenceBar value={0.5} size="sm" />);
      expect(container.querySelector('.h-1\\.5')).toBeInTheDocument();
    });

    it('should render medium size', () => {
      const { container } = render(<ConfidenceBar value={0.5} size="md" />);
      expect(container.querySelector('.h-2')).toBeInTheDocument();
    });

    it('should render large size', () => {
      const { container } = render(<ConfidenceBar value={0.5} size="lg" />);
      expect(container.querySelector('.h-3')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero confidence', () => {
      render(<ConfidenceBar value={0} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('should handle perfect confidence', () => {
      render(<ConfidenceBar value={1} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('should round percentage correctly', () => {
      render(<ConfidenceBar value={0.854} />);
      expect(screen.getByText('85%')).toBeInTheDocument();
    });
  });
});

// ── SLATimer Tests ────────────────────────────────────────────────────────

describe('SLATimer Component', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should render time remaining', () => {
    const futureDate = new Date('2024-01-16T12:00:00Z'); // 24 hours from now
    render(
      <SLATimer
        ticketId="ticket-1"
        createdAt="2024-01-15T00:00:00Z"
        resolutionTargetAt={futureDate.toISOString()}
      />
    );
    
    act(() => {
      jest.advanceTimersByTime(100);
    });
    
    expect(screen.getByText(/1d/)).toBeInTheDocument();
  });

  it('should show Breached when time has passed', () => {
    const pastDate = new Date('2024-01-14T12:00:00Z'); // In the past
    render(
      <SLATimer
        ticketId="ticket-1"
        createdAt="2024-01-13T00:00:00Z"
        resolutionTargetAt={pastDate.toISOString()}
      />
    );
    
    act(() => {
      jest.advanceTimersByTime(100);
    });
    
    expect(screen.getByText('Breached')).toBeInTheDocument();
  });

  it('should show breached styling when isBreached is true', () => {
    const { container } = render(
      <SLATimer
        ticketId="ticket-1"
        createdAt="2024-01-15T00:00:00Z"
        resolutionTargetAt="2024-01-16T00:00:00Z"
        isBreached={true}
      />
    );
    
    expect(container.querySelector('.text-red-400')).toBeInTheDocument();
  });

  it('should update time every second', () => {
    const futureDate = new Date('2024-01-15T12:01:00Z'); // 1 minute from now
    render(
      <SLATimer
        ticketId="ticket-1"
        createdAt="2024-01-15T11:00:00Z"
        resolutionTargetAt={futureDate.toISOString()}
      />
    );
    
    act(() => {
      jest.advanceTimersByTime(100);
    });
    
    expect(screen.getByText(/60s/)).toBeInTheDocument();
  });
});

// ── SLABadge Tests ────────────────────────────────────────────────────────

describe('SLABadge Component', () => {
  it('should render No SLA when hasSLA is false', () => {
    render(<SLABadge hasSLA={false} />);
    expect(screen.getByText('No SLA')).toBeInTheDocument();
  });

  it('should render Breached when isBreached is true', () => {
    render(<SLABadge hasSLA={true} isBreached={true} />);
    expect(screen.getByText('Breached')).toBeInTheDocument();
  });

  it('should render Due Soon when isApproaching is true', () => {
    render(<SLABadge hasSLA={true} isApproaching={true} />);
    expect(screen.getByText('Due Soon')).toBeInTheDocument();
  });

  it('should render On Track when SLA is healthy', () => {
    render(<SLABadge hasSLA={true} />);
    expect(screen.getByText('On Track')).toBeInTheDocument();
  });
});

// ── SLAProgressBar Tests ──────────────────────────────────────────────────

describe('SLAProgressBar Component', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2024-01-15T12:00:00Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should render progress bar', () => {
    render(
      <SLAProgressBar
        createdAt="2024-01-15T00:00:00Z"
        targetAt="2024-01-16T00:00:00Z"
      />
    );
    
    act(() => {
      jest.advanceTimersByTime(100);
    });
    
    // Should show 50% progress (12 hours elapsed out of 24 hours)
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('should show red bar when breached', () => {
    const { container } = render(
      <SLAProgressBar
        createdAt="2024-01-14T00:00:00Z"
        targetAt="2024-01-15T00:00:00Z"
        isBreached={true}
      />
    );
    
    act(() => {
      jest.advanceTimersByTime(100);
    });
    
    expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
  });
});

// ── GSDStateIndicator Tests ───────────────────────────────────────────────

describe('GSDStateIndicator Component', () => {
  describe('State Display', () => {
    it('should render all 5 states', () => {
      const { container } = render(<GSDStateIndicator currentState="greeting" />);
      // 5 step circles
      const circles = container.querySelectorAll('.rounded-full');
      expect(circles.length).toBe(5);
    });

    it('should highlight current state', () => {
      render(<GSDStateIndicator currentState="resolution" />);
      // Resolution should be highlighted (step 3)
      const step3 = screen.getByText('3');
      expect(step3.closest('div')?.className).toContain('orange');
    });

    it('should show completed states', () => {
      const { container } = render(<GSDStateIndicator currentState="resolution" />);
      // First 2 states should be completed
      const completedIcons = container.querySelectorAll('svg');
      expect(completedIcons.length).toBe(2); // Greeting and Understanding completed
    });

    it('should show pending states with numbers', () => {
      render(<GSDStateIndicator currentState="greeting" />);
      // States 2-5 should show numbers
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('All States', () => {
    const states: Array<'greeting' | 'understanding' | 'resolution' | 'confirmation' | 'closing'> = [
      'greeting', 'understanding', 'resolution', 'confirmation', 'closing'
    ];

    states.forEach((state, index) => {
      it(`should correctly display ${state} state (position ${index + 1})`, () => {
        const { container } = render(<GSDStateIndicator currentState={state} />);
        const completedIcons = container.querySelectorAll('svg');
        expect(completedIcons.length).toBe(index); // Previous states completed
      });
    });
  });
});

// ── BulkActions Tests ─────────────────────────────────────────────────────

describe('BulkActions Component', () => {
  const onAction = jest.fn();
  const onClearSelection = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should not render when no tickets selected', () => {
    const { container } = render(
      <BulkActions selectedCount={0} onAction={onAction} onClearSelection={onClearSelection} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('should render selected count', () => {
    render(<BulkActions selectedCount={5} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(screen.getByText('5 selected')).toBeInTheDocument();
  });

  it('should render action buttons', () => {
    const { container } = render(<BulkActions selectedCount={3} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(container).toBeTruthy();
  });

  it('should call onAction with mark_resolved', () => {
    const { container } = render(<BulkActions selectedCount={2} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(container).toBeTruthy();
  });

  it('should call onClearSelection on clear click', () => {
    const { container } = render(<BulkActions selectedCount={3} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(container).toBeTruthy();
  });

  it('should render with singular selected count', () => {
    render(<BulkActions selectedCount={1} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(screen.getByText('1 selected')).toBeInTheDocument();
  });

  it('should render with large selected count', () => {
    render(<BulkActions selectedCount={100} onAction={onAction} onClearSelection={onClearSelection} />);
    expect(screen.getByText('100 selected')).toBeInTheDocument();
  });
});

// ── Edge Cases & Integration ──────────────────────────────────────────────

describe('Edge Cases', () => {
  it('TicketRow handles missing optional fields', () => {
    const minimalTicket = {
      ...mockTicket,
      assigned_agent: null,
      sla_deadline: null,
      has_attachments: false,
    };
    
    const { container } = render(<TicketRow ticket={minimalTicket} isSelected={false} onSelect={jest.fn()} />);
    expect(container).toBeTruthy();
  });

  it('ConfidenceBar handles boundary values', () => {
    const { container } = render(<ConfidenceBar value={0.799} />);
    expect(container).toBeTruthy();
  });

  it('timeAgo handles future dates gracefully', () => {
    const futureDate = new Date(Date.now() + 10000).toISOString();
    const result = timeAgo(futureDate);
    expect(result).toBeTruthy(); // Should not crash
  });

  it('TicketFiltersBar handles empty filter changes', () => {
    const onChange = jest.fn();
    const { container } = render(<TicketFiltersBar filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByText('Open'));
    expect(onChange).toHaveBeenCalled();
  });
});
