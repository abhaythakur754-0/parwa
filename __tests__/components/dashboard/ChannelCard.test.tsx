/**
 * Unit Tests: ChannelCard Component
 *
 * Tests channel display, toggle, collapsible settings, connection test, and save behavior.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mocks ──────────────────────────────────────────────────────────────

jest.mock('@/lib/channels-api', () => ({
  __esModule: true,
}));

jest.mock('lucide-react', () => ({
  ChevronDown: () => <span data-testid="chevron-down" />,
  Loader2: () => <span data-testid="loader2" />,
  Plug: () => <span data-testid="plug" />,
  AlertCircle: () => <span data-testid="alert-circle" />,
  CheckCircle2: () => <span data-testid="check-circle-2" />,
  XCircle: () => <span data-testid="x-circle" />,
}));

jest.mock('@/components/ui/badge', () => ({
  Badge: ({ children, ...props }: any) => <span data-testid="badge">{children}</span>,
}));

jest.mock('@/components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, ...props }: any) => (
    <button
      data-testid="switch"
      checked={checked}
      onClick={() => onCheckedChange?.(!checked)}
      aria-label={props['aria-label']}
    />
  ),
}));

jest.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, ...props }: any) => (
    <button
      data-testid="button"
      onClick={onClick}
      disabled={disabled}
      className={className}
    >
      {children}
    </button>
  ),
}));

jest.mock('@/components/ui/collapsible', () => ({
  Collapsible: ({ children, open, onOpenChange }: any) => (
    <div data-testid="collapsible" data-open={open}>
      {children}
    </div>
  ),
  CollapsibleContent: ({ children }: any) => (
    <div data-testid="collapsible-content">{children}</div>
  ),
  CollapsibleTrigger: ({ children, asChild, ...props }: any) => (
    <div data-testid="collapsible-trigger">{children}</div>
  ),
}));

import ChannelCard from '@/components/dashboard/ChannelCard';

// ── Test Data ──────────────────────────────────────────────────────────

const mockChannel = {
  channel_type: 'email',
  channel_category: 'email',
  description: 'Email support channel for customer inquiries',
  is_enabled: true,
  auto_create_ticket: true,
  char_limit: 500,
  allowed_file_types: ['pdf', 'doc', 'png'],
  max_file_size: 5242880, // 5MB
};

const defaultProps = {
  channel: mockChannel,
  onToggle: jest.fn(),
  onSave: jest.fn(),
  onTest: jest.fn(),
  isSaving: false,
};

// ── Test Suite ────────────────────────────────────────────────────────

describe('ChannelCard Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders channel type', () => {
      render(<ChannelCard {...defaultProps} />);
      // 'email' appears as both the channel type heading and category badge
      const emailElements = screen.getAllByText('email');
      expect(emailElements.length).toBeGreaterThanOrEqual(1);
    });

    it('renders channel description', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(
        screen.getByText('Email support channel for customer inquiries')
      ).toBeInTheDocument();
    });

    it('renders channel icon', () => {
      render(<ChannelCard {...defaultProps} />);
      // Email icon is the ✉️ emoji
      expect(screen.getByText('✉️')).toBeInTheDocument();
    });

    it('renders category badge', () => {
      render(<ChannelCard {...defaultProps} />);
      const badges = screen.getAllByTestId('badge');
      expect(badges.length).toBeGreaterThanOrEqual(1);
      expect(badges[0].textContent).toBe('email');
    });
  });

  // ── Status Indicator ───────────────────────────────────────────────

  describe('Status Indicator', () => {
    it('renders "Active" status when channel is enabled', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('renders "Disabled" status when channel is disabled', () => {
      render(
        <ChannelCard
          {...defaultProps}
          channel={{ ...mockChannel, is_enabled: false }}
        />
      );
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    it('applies opacity-80 when channel is disabled', () => {
      const { container } = render(
        <ChannelCard
          {...defaultProps}
          channel={{ ...mockChannel, is_enabled: false }}
        />
      );
      const card = container.querySelector('.opacity-80');
      expect(card).toBeInTheDocument();
    });

    it('does not apply opacity-80 when channel is enabled', () => {
      const { container } = render(<ChannelCard {...defaultProps} />);
      const card = container.querySelector('.opacity-80');
      expect(card).toBeNull();
    });
  });

  // ── Toggle Switch ──────────────────────────────────────────────────

  describe('Toggle Switch', () => {
    it('renders toggle switch', () => {
      render(<ChannelCard {...defaultProps} />);
      const switches = screen.getAllByTestId('switch');
      expect(switches.length).toBeGreaterThanOrEqual(1);
    });

    it('toggle switch has correct aria-label', () => {
      render(<ChannelCard {...defaultProps} />);
      const switches = screen.getAllByTestId('switch');
      // First switch is the channel enable/disable toggle
      expect(switches[0]).toHaveAttribute('aria-label', 'Toggle email');
    });

    it('calls onToggle when switch is clicked', () => {
      render(<ChannelCard {...defaultProps} />);
      const switches = screen.getAllByTestId('switch');
      fireEvent.click(switches[0]);
      expect(defaultProps.onToggle).toHaveBeenCalledWith('email', false);
    });
  });

  // ── Collapsible ────────────────────────────────────────────────────

  describe('Collapsible', () => {
    it('renders Collapsible component', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByTestId('collapsible')).toBeInTheDocument();
    });

    it('renders CollapsibleTrigger', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByTestId('collapsible-trigger')).toBeInTheDocument();
    });

    it('renders ChevronDown icon', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByTestId('chevron-down')).toBeInTheDocument();
    });
  });

  // ── Connection Test ────────────────────────────────────────────────

  describe('Connection Test', () => {
    it('renders Test Connection button', () => {
      render(<ChannelCard {...defaultProps} />);
      const buttons = screen.getAllByTestId('button');
      const testBtn = buttons.find((btn) =>
        btn.textContent?.includes('Test Connection')
      );
      expect(testBtn).toBeDefined();
    });

    it('shows Loader2 when testing connection', async () => {
      const mockTest = jest.fn().mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(null), 100))
      );
      render(
        <ChannelCard {...defaultProps} onTest={mockTest} />
      );

      const buttons = screen.getAllByTestId('button');
      const testBtn = buttons.find((btn) =>
        btn.textContent?.includes('Test Connection')
      )!;

      // First, we need to open the collapsible to see the test button
      // Since CollapsibleTrigger wraps the card header button, clicking the trigger
      // would open the content. But our mock Collapsible always renders content.
      // The Test Connection button is inside CollapsibleContent which is always rendered.
      fireEvent.click(testBtn);

      await waitFor(() => {
        expect(screen.getByTestId('loader2')).toBeInTheDocument();
      });
    });
  });

  // ── Save Button ────────────────────────────────────────────────────

  describe('Save Button', () => {
    it('renders Save Configuration button', () => {
      render(<ChannelCard {...defaultProps} />);
      const buttons = screen.getAllByTestId('button');
      const saveBtn = buttons.find((btn) =>
        btn.textContent?.includes('Save Configuration')
      );
      expect(saveBtn).toBeDefined();
    });

    it('save button is disabled when no changes', () => {
      render(<ChannelCard {...defaultProps} />);
      const buttons = screen.getAllByTestId('button');
      const saveBtn = buttons.find((btn) =>
        btn.textContent?.includes('Save Configuration')
      )!;
      expect(saveBtn).toBeDisabled();
    });
  });

  // ── Settings Form ──────────────────────────────────────────────────

  describe('Settings Form', () => {
    it('renders Character Limit input', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByLabelText('Character Limit')).toBeInTheDocument();
    });

    it('renders Allowed File Types input', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByLabelText('Allowed File Types')).toBeInTheDocument();
    });

    it('renders Max File Size input', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByLabelText('Max File Size')).toBeInTheDocument();
    });

    it('renders Auto-create Tickets label', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByText('Auto-create Tickets')).toBeInTheDocument();
    });

    it('shows Connection Status label', () => {
      render(<ChannelCard {...defaultProps} />);
      expect(screen.getByText('Connection Status')).toBeInTheDocument();
    });
  });
});
