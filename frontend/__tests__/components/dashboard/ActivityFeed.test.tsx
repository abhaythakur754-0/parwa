/**
 * Day 16 — Unit Tests: ActivityFeed Component (F-037)
 *
 * Tests the ActivityFeed component rendering, filtering,
 * pagination, and empty states.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the dashboardApi before importing the component
jest.mock('@/lib/analytics-api', () => ({
  dashboardApi: {
    getActivityFeed: jest.fn(),
  },
}));

import ActivityFeed from '@/components/dashboard/ActivityFeed';
import { dashboardApi } from '@/lib/analytics-api';
import type { ActivityEvent } from '@/types/analytics';

// ── Test Data ─────────────────────────────────────────────────────────

const mockEvents: ActivityEvent[] = [
  {
    event_id: 'evt-001',
    event_type: 'ticket_created',
    actor_type: 'customer',
    actor_name: 'John Doe',
    description: 'New ticket created: Login issue',
    ticket_id: 'ticket-123',
    ticket_subject: 'Login issue',
    metadata: { priority: 'high', category: 'auth' },
    created_at: new Date(Date.now() - 5 * 60000).toISOString(), // 5 min ago
  },
  {
    event_id: 'evt-002',
    event_type: 'status_changed',
    actor_type: 'ai',
    actor_name: 'PARWA AI',
    description: 'Status changed from open to in_progress',
    ticket_id: 'ticket-123',
    metadata: { from: 'open', to: 'in_progress' },
    created_at: new Date(Date.now() - 10 * 60000).toISOString(), // 10 min ago
  },
  {
    event_id: 'evt-003',
    event_type: 'assigned',
    actor_type: 'system',
    description: 'Ticket assigned to ai',
    ticket_id: 'ticket-456',
    metadata: { assignee_type: 'ai', score: 0.92 },
    created_at: new Date(Date.now() - 30 * 60000).toISOString(), // 30 min ago
  },
  {
    event_id: 'evt-004',
    event_type: 'resolved',
    actor_type: 'ai',
    actor_name: 'PARWA AI',
    description: 'Ticket resolved by AI',
    ticket_id: 'ticket-789',
    ticket_subject: 'Password reset',
    metadata: {},
    created_at: new Date(Date.now() - 2 * 3600000).toISOString(), // 2 hours ago
  },
  {
    event_id: 'evt-005',
    event_type: 'sla_warning',
    actor_type: 'system',
    description: 'SLA approaching for ticket',
    ticket_id: 'ticket-999',
    metadata: {},
    created_at: new Date(Date.now() - 3 * 3600000).toISOString(), // 3 hours ago
  },
];

// ── Test Suite ────────────────────────────────────────────────────────

describe('ActivityFeed Component (F-037)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the activity feed header', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      expect(screen.getByText('Activity Feed')).toBeInTheDocument();
    });

    it('renders all initial events', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      // Each event's description should be present
      expect(screen.getByText('New ticket created: Login issue')).toBeInTheDocument();
      expect(screen.getByText('Status changed from open to in_progress')).toBeInTheDocument();
      expect(screen.getByText('Ticket assigned to ai')).toBeInTheDocument();
      expect(screen.getByText('Ticket resolved by AI')).toBeInTheDocument();
      expect(screen.getByText('SLA approaching for ticket')).toBeInTheDocument();
    });

    it('shows the event count badge when initialEvents provided', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('renders actor badges', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      // PARWA AI appears in both actor badges and descriptions, use getAllByText
      const parwaBadges = screen.getAllByText('PARWA AI');
      expect(parwaBadges.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('renders ticket subject links', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      // These are inside <a> tags with truncate
      const loginLinks = screen.getAllByText('Login issue');
      expect(loginLinks.length).toBeGreaterThanOrEqual(1);
      const passwordLinks = screen.getAllByText('Password reset');
      expect(passwordLinks.length).toBeGreaterThanOrEqual(1);
    });

    it('renders relative timestamps', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      expect(screen.getByText('5m ago')).toBeInTheDocument();
      expect(screen.getByText('10m ago')).toBeInTheDocument();
      expect(screen.getByText('30m ago')).toBeInTheDocument();
      expect(screen.getByText('2h ago')).toBeInTheDocument();
    });
  });

  // ── Filter Tabs ─────────────────────────────────────────────────────

  describe('Filter Tabs', () => {
    it('renders filter tabs by default', () => {
      render(<ActivityFeed initialEvents={mockEvents} showFilters={true} />);
      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Created')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Assigned')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });

    it('hides filter tabs when showFilters is false', () => {
      render(<ActivityFeed initialEvents={mockEvents} showFilters={false} />);
      expect(screen.queryByText('All')).not.toBeInTheDocument();
    });

    it('highlights active filter tab', () => {
      render(<ActivityFeed initialEvents={mockEvents} />);
      const allTab = screen.getByText('All');
      expect(allTab).toHaveClass('text-[#FF7F11]');
    });

    it('calls API when filter is clicked (without initial events)', async () => {
      const mockResponse = {
        events: [mockEvents[0]],
        total: 1,
        page: 1,
        page_size: 25,
        has_more: false,
      };
      (dashboardApi.getActivityFeed as jest.Mock).mockResolvedValue(mockResponse);

      render(<ActivityFeed initialEvents={[]} />);

      // Wait for initial fetch
      await waitFor(() => {
        expect(dashboardApi.getActivityFeed).toHaveBeenCalled();
      });

      // Click a filter
      const createdFilter = screen.getByText('Created');
      fireEvent.click(createdFilter);

      await waitFor(() => {
        expect(dashboardApi.getActivityFeed).toHaveBeenCalledWith(
          expect.objectContaining({ eventType: 'ticket_created' })
        );
      });
    });
  });

  // ── Empty State ─────────────────────────────────────────────────────

  describe('Empty State', () => {
    it('shows empty state when no events', async () => {
      (dashboardApi.getActivityFeed as jest.Mock).mockResolvedValue({
        events: [],
        total: 0,
        page: 1,
        page_size: 25,
        has_more: false,
      });

      render(<ActivityFeed initialEvents={[]} />);

      await waitFor(() => {
        expect(screen.getByText('No activity yet')).toBeInTheDocument();
      });
    });

    it('shows empty state helper text', async () => {
      (dashboardApi.getActivityFeed as jest.Mock).mockResolvedValue({
        events: [],
        total: 0,
        page: 1,
        page_size: 25,
        has_more: false,
      });

      render(<ActivityFeed initialEvents={[]} />);

      await waitFor(() => {
        expect(screen.getByText(/Events will appear here/)).toBeInTheDocument();
      });
    });
  });

  // ── Pagination (Load More) ─────────────────────────────────────────

  describe('Pagination', () => {
    it('shows load more button when has_more is true (no initial events)', async () => {
      (dashboardApi.getActivityFeed as jest.Mock).mockResolvedValue({
        events: mockEvents.slice(0, 2),
        total: 10,
        page: 1,
        page_size: 2,
        has_more: true,
      });

      render(<ActivityFeed initialEvents={[]} />);

      await waitFor(() => {
        expect(screen.getByText(/Load more/)).toBeInTheDocument();
      });
    });

    it('shows remaining count in load more button', async () => {
      (dashboardApi.getActivityFeed as jest.Mock).mockResolvedValue({
        events: mockEvents.slice(0, 2),
        total: 10,
        page: 1,
        page_size: 2,
        has_more: true,
      });

      render(<ActivityFeed initialEvents={[]} />);

      await waitFor(() => {
        expect(screen.getByText('Load more (8 remaining)')).toBeInTheDocument();
      });
    });

    it('fetches next page on load more click', async () => {
      (dashboardApi.getActivityFeed as jest.Mock)
        .mockResolvedValueOnce({
          events: mockEvents.slice(0, 2),
          total: 10,
          page: 1,
          page_size: 2,
          has_more: true,
        })
        .mockResolvedValueOnce({
          events: mockEvents.slice(2, 4),
          total: 10,
          page: 2,
          page_size: 2,
          has_more: true,
        });

      render(<ActivityFeed initialEvents={[]} />);

      await waitFor(() => {
        expect(screen.getByText(/Load more/)).toBeInTheDocument();
      });

      const loadMoreBtn = screen.getByText(/Load more/);
      fireEvent.click(loadMoreBtn);

      await waitFor(() => {
        expect(dashboardApi.getActivityFeed).toHaveBeenCalledTimes(2);
        expect(dashboardApi.getActivityFeed).toHaveBeenLastCalledWith(
          expect.objectContaining({ page: 2 })
        );
      });
    });
  });

  // ── Event Type Icons ────────────────────────────────────────────────

  describe('Event Type Icons', () => {
    it('renders different event types with correct colors', () => {
      const { container } = render(<ActivityFeed initialEvents={mockEvents} />);

      // ticket_created should have sky color
      const createdIcons = container.querySelectorAll('.text-sky-400');
      expect(createdIcons.length).toBeGreaterThanOrEqual(1);

      // status_changed should have amber color
      const statusIcons = container.querySelectorAll('.text-amber-400');
      expect(statusIcons.length).toBeGreaterThanOrEqual(1);

      // resolved should have emerald color
      const resolvedIcons = container.querySelectorAll('.text-emerald-400');
      expect(resolvedIcons.length).toBeGreaterThanOrEqual(1);
    });
  });
});
