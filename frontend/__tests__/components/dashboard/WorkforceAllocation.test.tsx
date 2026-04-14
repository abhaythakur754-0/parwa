/**
 * Day 16 — Unit Tests: WorkforceAllocation Component (F-041)
 *
 * Tests the WorkforceAllocation component rendering, tabs,
 * channel/category breakdowns, and empty states.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the API
jest.mock('@/lib/api', () => ({
  get: jest.fn(),
}));

import WorkforceAllocation from '@/components/dashboard/WorkforceAllocation';
import { get } from '@/lib/api';

// ── Mock Data ─────────────────────────────────────────────────────────

const mockWorkforceData = {
  current_split: {
    period: '2025-03-16 to 2025-04-15',
    date: '2025-04-15',
    ai_tickets: 450,
    human_tickets: 180,
    ai_pct: 71.4,
    human_pct: 28.6,
    total: 630,
  },
  daily_trend: Array.from({ length: 30 }, (_, i) => ({
    period: `Day ${i + 1}`,
    date: `2025-03-${(16 + i) > 31 ? (16 + i - 31) : (16 + i)}`,
    ai_tickets: Math.floor(Math.random() * 20) + 5,
    human_tickets: Math.floor(Math.random() * 10) + 2,
    ai_pct: 65 + Math.random() * 15,
    human_pct: 20 + Math.random() * 10,
    total: 0,
  })),
  by_channel: {
    email: { period: '', date: '', ai_tickets: 200, human_tickets: 80, ai_pct: 71.4, human_pct: 28.6, total: 280 },
    chat: { period: '', date: '', ai_tickets: 150, human_tickets: 60, ai_pct: 71.4, human_pct: 28.6, total: 210 },
    sms: { period: '', date: '', ai_tickets: 50, human_tickets: 20, ai_pct: 71.4, human_pct: 28.6, total: 70 },
  },
  by_category: [
    { category: 'Billing', total_tickets: 180, ai_tickets: 120, human_tickets: 60, ai_pct: 66.7, human_pct: 33.3 },
    { category: 'Technical', total_tickets: 150, ai_tickets: 110, human_tickets: 40, ai_pct: 73.3, human_pct: 26.7 },
    { category: 'General', total_tickets: 120, ai_tickets: 80, human_tickets: 40, ai_pct: 66.7, human_pct: 33.3 },
  ],
  ai_resolution_rate: 87.5,
  human_resolution_rate: 92.1,
};

// ── Test Suite ────────────────────────────────────────────────────────

describe('WorkforceAllocation Component (F-041)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering with initialData', () => {
    it('renders the header', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('Workforce Allocation')).toBeInTheDocument();
    });

    it('renders AI vs Human split percentages', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('71.4%')).toBeInTheDocument();
      expect(screen.getByText('28.6%')).toBeInTheDocument();
    });

    it('renders total ticket count', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('630 total tickets')).toBeInTheDocument();
    });

    it('renders AI resolution rate', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('87.5%')).toBeInTheDocument();
    });

    it('renders human resolution rate', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('92.1%')).toBeInTheDocument();
    });

    it('renders daily trend label', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('Daily Trend (Last 7 days)')).toBeInTheDocument();
    });
  });

  describe('View Tabs', () => {
    it('renders three tabs', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      expect(screen.getByText('overview')).toBeInTheDocument();
      expect(screen.getByText('channels')).toBeInTheDocument();
      expect(screen.getByText('categories')).toBeInTheDocument();
    });

    it('switches to channels tab', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      fireEvent.click(screen.getByText('channels'));
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('Chat')).toBeInTheDocument();
      expect(screen.getByText('SMS')).toBeInTheDocument();
    });

    it('shows channel ticket counts', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      fireEvent.click(screen.getByText('channels'));
      expect(screen.getByText('280 tickets')).toBeInTheDocument();
      expect(screen.getByText('210 tickets')).toBeInTheDocument();
      expect(screen.getByText('70 tickets')).toBeInTheDocument();
    });

    it('switches to categories tab', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      fireEvent.click(screen.getByText('categories'));
      expect(screen.getByText('Billing')).toBeInTheDocument();
      expect(screen.getByText('Technical')).toBeInTheDocument();
      expect(screen.getByText('General')).toBeInTheDocument();
    });

    it('shows category AI percentages', () => {
      render(<WorkforceAllocation initialData={mockWorkforceData} />);
      fireEvent.click(screen.getByText('categories'));
      // 66.7% appears in both Billing and General categories
      const sixtySix = screen.getAllByText('66.7% AI');
      expect(sixtySix.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('73.3% AI')).toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no data', async () => {
      (get as jest.Mock).mockRejectedValue(new Error('API error'));
      render(<WorkforceAllocation />);

      await waitFor(() => {
        expect(screen.getByText('No allocation data yet')).toBeInTheDocument();
      });
    });

    it('shows empty channels state', () => {
      const noChannels = { ...mockWorkforceData, by_channel: {} };
      render(<WorkforceAllocation initialData={noChannels} />);
      fireEvent.click(screen.getByText('channels'));
      expect(screen.getByText('No channel data yet')).toBeInTheDocument();
    });

    it('shows empty categories state', () => {
      const noCategories = { ...mockWorkforceData, by_category: [] };
      render(<WorkforceAllocation initialData={noCategories} />);
      fireEvent.click(screen.getByText('categories'));
      expect(screen.getByText('No category data yet')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows skeleton when loading', () => {
      (get as jest.Mock).mockReturnValue(new Promise(() => {}));
      render(<WorkforceAllocation />);
      const skeletonElements = document.querySelectorAll('.animate-pulse');
      expect(skeletonElements.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('handles zero total tickets', () => {
      const zeroData = {
        ...mockWorkforceData,
        current_split: { ...mockWorkforceData.current_split, ai_pct: 0, human_pct: 0, total: 0 },
      };
      render(<WorkforceAllocation initialData={zeroData} />);
      expect(screen.getByText('Workforce Allocation')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <WorkforceAllocation initialData={mockWorkforceData} className="mt-4" />
      );
      expect(container.firstChild).toHaveClass('mt-4');
    });
  });
});
