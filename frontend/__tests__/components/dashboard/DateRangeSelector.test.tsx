/**
 * Unit Tests: DateRangeSelector Component
 *
 * Tests preset rendering, active state, onChange calls, and a11y attributes.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import DateRangeSelector from '@/components/dashboard/DateRangeSelector';

// ── Test Suite ────────────────────────────────────────────────────────

describe('DateRangeSelector Component', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Rendering Presets ──────────────────────────────────────────────

  describe('Rendering Presets', () => {
    it('renders "Today" preset', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      expect(screen.getByText('Today')).toBeInTheDocument();
    });

    it('renders "Last 7 Days" preset', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      expect(screen.getByText('Last 7 Days')).toBeInTheDocument();
    });

    it('renders "Last 30 Days" preset', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      expect(screen.getByText('Last 30 Days')).toBeInTheDocument();
    });

    it('renders "Last 90 Days" preset', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      expect(screen.getByText('Last 90 Days')).toBeInTheDocument();
    });

    it('renders all 4 presets', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      const buttons = screen.getAllByRole('tab');
      expect(buttons.length).toBe(4);
    });
  });

  // ── Active Preset Styling ──────────────────────────────────────────

  describe('Active Preset', () => {
    it('highlights active preset with orange text', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      const activeBtn = screen.getByText('Today');
      expect(activeBtn).toHaveClass('text-orange-400');
    });

    it('highlights active preset with orange background', () => {
      render(<DateRangeSelector value="7d" onChange={mockOnChange} />);
      const activeBtn = screen.getByText('Last 7 Days');
      expect(activeBtn).toHaveClass('bg-orange-500/15');
    });

    it('inactive preset has zinc-500 text', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      const inactiveBtn = screen.getByText('Last 30 Days');
      expect(inactiveBtn).toHaveClass('text-zinc-500');
    });

    it('switches active preset when value changes', () => {
      const { rerender } = render(
        <DateRangeSelector value="30d" onChange={mockOnChange} />
      );
      let active30d = screen.getByText('Last 30 Days');
      expect(active30d).toHaveClass('text-orange-400');

      rerender(
        <DateRangeSelector value="90d" onChange={mockOnChange} />
      );
      let active90d = screen.getByText('Last 90 Days');
      expect(active90d).toHaveClass('text-orange-400');

      let inactive30d = screen.getByText('Last 30 Days');
      expect(inactive30d).toHaveClass('text-zinc-500');
    });
  });

  // ── onChange Behavior ──────────────────────────────────────────────

  describe('onChange Behavior', () => {
    it('calls onChange when "Today" is clicked', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      fireEvent.click(screen.getByText('Today'));
      expect(mockOnChange).toHaveBeenCalledTimes(1);
    });

    it('calls onChange with correct date range for "7d"', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      fireEvent.click(screen.getByText('Last 7 Days'));

      const calledArg = mockOnChange.mock.calls[0][0];
      expect(calledArg).toHaveProperty('start_date');
      expect(calledArg).toHaveProperty('end_date');
      // Verify start_date is a date string in YYYY-MM-DD format
      expect(calledArg.start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(calledArg.end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('calls onChange with correct date range for "90d"', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      fireEvent.click(screen.getByText('Last 90 Days'));

      const calledArg = mockOnChange.mock.calls[0][0];
      expect(calledArg).toHaveProperty('start_date');
      expect(calledArg).toHaveProperty('end_date');
    });

    it('start_date is before end_date for "30d"', () => {
      render(<DateRangeSelector value="today" onChange={mockOnChange} />);
      fireEvent.click(screen.getByText('Last 30 Days'));

      const { start_date, end_date } = mockOnChange.mock.calls[0][0];
      expect(new Date(start_date).getTime()).toBeLessThanOrEqual(
        new Date(end_date).getTime()
      );
    });
  });

  // ── Accessibility ──────────────────────────────────────────────────

  describe('Accessibility', () => {
    it('has role="tablist" on container', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      expect(screen.getByRole('tablist')).toBeInTheDocument();
    });

    it('has aria-label="Date range" on tablist', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'Date range');
    });

    it('has aria-selected="true" on active tab', () => {
      render(<DateRangeSelector value="7d" onChange={mockOnChange} />);
      const activeTab = screen.getByText('Last 7 Days');
      expect(activeTab).toHaveAttribute('aria-selected', 'true');
    });

    it('has aria-selected="false" on inactive tabs', () => {
      render(<DateRangeSelector value="7d" onChange={mockOnChange} />);
      const inactiveTab = screen.getByText('Today');
      expect(inactiveTab).toHaveAttribute('aria-selected', 'false');
    });

    it('all buttons have role="tab"', () => {
      render(<DateRangeSelector value="30d" onChange={mockOnChange} />);
      const tabs = screen.getAllByRole('tab');
      expect(tabs.length).toBe(4);
    });
  });

  // ── Custom className ───────────────────────────────────────────────

  describe('Custom className', () => {
    it('applies custom className', () => {
      const { container } = render(
        <DateRangeSelector
          value="30d"
          onChange={mockOnChange}
          className="my-custom-class"
        />
      );
      const tablist = screen.getByRole('tablist');
      expect(tablist.className).toContain('my-custom-class');
    });
  });
});
