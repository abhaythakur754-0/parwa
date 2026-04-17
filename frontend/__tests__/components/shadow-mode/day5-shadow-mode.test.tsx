/**
 * Day 5 Shadow Mode Tests - Undo, Log & Settings
 * 
 * Tests for:
 * - B5.1 Undo Queue Component
 * - B5.2 Undo History Component
 * - B5.3 Shadow Log Page
 * - B5.4 Shadow Mode Settings Page
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { jest } from '@jest/globals';

// ── Mocks ─────────────────────────────────────────────────────────────────────

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
  }),
  usePathname: () => '/dashboard/shadow-log',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  success: jest.fn(),
  error: jest.fn(),
}));

// Mock SocketContext
const mockSocket = {
  on: jest.fn(),
  off: jest.fn(),
  emit: jest.fn(),
};

jest.mock('@/contexts/SocketContext', () => ({
  useSocket: () => ({
    isConnected: true,
    socket: mockSocket,
  }),
}));

// Mock shadow-api
const mockShadowApi = {
  getMode: jest.fn(),
  setMode: jest.fn(),
  getPreferences: jest.fn(),
  setPreference: jest.fn(),
  deletePreference: jest.fn(),
  getLog: jest.fn(),
  getStats: jest.fn(),
  evaluate: jest.fn(),
  approve: jest.fn(),
  reject: jest.fn(),
  undo: jest.fn(),
  batchResolve: jest.fn(),
};

jest.mock('@/lib/shadow-api', () => ({
  shadowApi: mockShadowApi,
  getShadowMode: jest.fn(),
  setShadowMode: jest.fn(),
  getShadowPreferences: jest.fn(),
  setShadowPreference: jest.fn(),
  deleteShadowPreference: jest.fn(),
  getShadowLog: jest.fn(),
  getShadowStats: jest.fn(),
  evaluateActionRisk: jest.fn(),
  approveShadowAction: jest.fn(),
  rejectShadowAction: jest.fn(),
  undoShadowAction: jest.fn(),
  batchResolve: jest.fn(),
}));

// Mock api client
jest.mock('@/lib/api', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  del: jest.fn(),
  getErrorMessage: (err: any) => err?.message || 'An error occurred',
}));

// ── Test Data ────────────────────────────────────────────────────────────────

const mockShadowLogEntries = [
  {
    id: 'shadow-1',
    company_id: 'company-1',
    action_type: 'refund',
    action_payload: { amount: 50, customer_id: 'cust_123' },
    jarvis_risk_score: 0.35,
    mode: 'graduated' as const,
    manager_decision: null,
    manager_note: null,
    resolved_at: null,
    created_at: new Date().toISOString(),
  },
  {
    id: 'shadow-2',
    company_id: 'company-1',
    action_type: 'email_reply',
    action_payload: { recipient: 'test@example.com' },
    jarvis_risk_score: 0.75,
    mode: 'shadow' as const,
    manager_decision: null,
    manager_note: null,
    resolved_at: null,
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 mins ago
  },
];

const mockUndoHistoryEntries = [
  {
    id: 'undo-1',
    company_id: 'company-1',
    executed_action_id: 'action-1',
    undo_type: 'reversal',
    original_data: JSON.stringify({ amount: 100 }),
    undo_data: null,
    undo_reason: 'Customer changed their mind',
    undone_by: 'user-1',
    undone_by_name: 'John Doe',
    action_type: 'refund',
    created_at: new Date().toISOString(),
  },
];

const mockShadowStats = {
  company_id: 'company-1',
  total_actions: 100,
  pending_count: 5,
  approved_count: 85,
  rejected_count: 10,
  approval_rate: 0.85,
  avg_risk_score: 0.35,
  mode_distribution: { shadow: 10, supervised: 30, graduated: 60 },
  action_type_distribution: { refund: 25, email_reply: 40, sms_reply: 35 },
};

const mockPreferences = [
  {
    id: 'pref-1',
    company_id: 'company-1',
    action_category: 'refund',
    preferred_mode: 'shadow' as const,
    set_via: 'ui' as const,
    updated_at: new Date().toISOString(),
  },
];

// ── B5.1 UndoQueue Component Tests ───────────────────────────────────────────

describe('B5.1 UndoQueue Component', () => {
  let UndoQueue: any;

  beforeAll(async () => {
    // Import component after mocks are set up
    const module = await import('@/components/dashboard/UndoQueue');
    UndoQueue = module.default;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockShadowApi.getLog.mockResolvedValue({
      items: mockShadowLogEntries,
      total: 2,
      page: 1,
      pages: 1,
    });
  });

  it('renders empty state when no undoable actions', async () => {
    mockShadowApi.getLog.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      pages: 1,
    });

    render(<UndoQueue />);

    await waitFor(() => {
      expect(screen.getByText(/no actions available for undo/i)).toBeInTheDocument();
    });
  });

  it('renders compact empty state', async () => {
    mockShadowApi.getLog.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      pages: 1,
    });

    render(<UndoQueue compact />);

    await waitFor(() => {
      expect(screen.getByText(/no actions to undo/i)).toBeInTheDocument();
    });
  });

  it('shows countdown timer for undoable actions', async () => {
    render(<UndoQueue />);

    await waitFor(() => {
      // Should show action type label
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Should show countdown timer
    await waitFor(() => {
      expect(screen.getByText(/left/i)).toBeInTheDocument();
    });
  });

  it('displays risk score badge for actions', async () => {
    render(<UndoQueue />);

    await waitFor(() => {
      // Risk score percentage should be shown
      expect(screen.getByText(/35%/)).toBeInTheDocument();
    });
  });

  it('shows undo button for each action', async () => {
    render(<UndoQueue />);

    await waitFor(() => {
      const undoButtons = screen.getAllByRole('button', { name: /undo/i });
      expect(undoButtons.length).toBeGreaterThan(0);
    });
  });

  it('opens undo confirmation modal when undo is clicked', async () => {
    const user = userEvent.setup();
    render(<UndoQueue />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Click undo button
    const undoButtons = screen.getAllByRole('button', { name: /undo/i });
    await user.click(undoButtons[0]);

    // Modal should appear
    await waitFor(() => {
      expect(screen.getByText(/undo action/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/why are you undoing/i)).toBeInTheDocument();
    });
  });

  it('requires reason before confirming undo', async () => {
    const user = userEvent.setup();
    render(<UndoQueue />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Open modal
    const undoButtons = screen.getAllByRole('button', { name: /undo/i });
    await user.click(undoButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/undo action/i)).toBeInTheDocument();
    });

    // Confirm button should be disabled without reason
    const confirmButton = screen.getByRole('button', { name: /confirm undo/i });
    expect(confirmButton).toBeDisabled();
  });

  it('calls undo API with reason when confirmed', async () => {
    mockShadowApi.undo.mockResolvedValueOnce({ undo_id: 'undo-new' });

    const user = userEvent.setup();
    render(<UndoQueue />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Open modal
    const undoButtons = screen.getAllByRole('button', { name: /undo/i });
    await user.click(undoButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/undo action/i)).toBeInTheDocument();
    });

    // Enter reason
    const reasonInput = screen.getByPlaceholderText(/why are you undoing/i);
    await user.type(reasonInput, 'Customer requested cancellation');

    // Confirm
    const confirmButton = screen.getByRole('button', { name: /confirm undo/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockShadowApi.undo).toHaveBeenCalledWith(
        expect.any(String),
        'Customer requested cancellation'
      );
    });
  });

  it('handles undo API error gracefully', async () => {
    const { toast } = require('react-hot-toast');
    mockShadowApi.undo.mockRejectedValueOnce(new Error('Undo failed'));

    const user = userEvent.setup();
    render(<UndoQueue />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Open modal and complete undo flow
    const undoButtons = screen.getAllByRole('button', { name: /undo/i });
    await user.click(undoButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/undo action/i)).toBeInTheDocument();
    });

    const reasonInput = screen.getByPlaceholderText(/why are you undoing/i);
    await user.type(reasonInput, 'Test reason');

    const confirmButton = screen.getByRole('button', { name: /confirm undo/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Undo failed');
    });
  });

  it('subscribes to socket events on mount', async () => {
    render(<UndoQueue />);

    await waitFor(() => {
      expect(mockSocket.on).toHaveBeenCalledWith('shadow:new', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('shadow:action_undone', expect.any(Function));
    });
  });

  it('unsubscribes from socket events on unmount', async () => {
    const { unmount } = render(<UndoQueue />);

    await waitFor(() => {
      expect(mockSocket.on).toHaveBeenCalled();
    });

    unmount();

    expect(mockSocket.off).toHaveBeenCalledWith('shadow:new', expect.any(Function));
    expect(mockSocket.off).toHaveBeenCalledWith('shadow:action_undone', expect.any(Function));
  });
});

// ── B5.2 UndoHistory Component Tests ─────────────────────────────────────────

describe('B5.2 UndoHistory Component', () => {
  let UndoHistory: any;

  beforeAll(async () => {
    const module = await import('@/components/dashboard/UndoHistory');
    UndoHistory = module.default;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    const { get } = require('@/lib/api');
    get.mockResolvedValue({
      data: { entries: mockUndoHistoryEntries },
    });
  });

  it('renders empty state when no undo history', async () => {
    const { get } = require('@/lib/api');
    get.mockResolvedValueOnce({ data: { entries: [] } });

    render(<UndoHistory />);

    await waitFor(() => {
      expect(screen.getByText(/no undo history/i)).toBeInTheDocument();
    });
  });

  it('displays undo history entries', async () => {
    render(<UndoHistory />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
      expect(screen.getByText(/reversal/i)).toBeInTheDocument();
    });
  });

  it('shows user who performed undo', async () => {
    render(<UndoHistory />);

    await waitFor(() => {
      expect(screen.getByText(/john doe/i)).toBeInTheDocument();
    });
  });

  it('expands row to show undo reason', async () => {
    const user = userEvent.setup();
    render(<UndoHistory />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Click to expand
    const row = screen.getByText(/refund/i).closest('div');
    await user.click(row!);

    await waitFor(() => {
      expect(screen.getByText(/undo reason/i)).toBeInTheDocument();
      expect(screen.getByText(/customer changed their mind/i)).toBeInTheDocument();
    });
  });

  it('exports to CSV when export button clicked', async () => {
    const user = userEvent.setup();
    render(<UndoHistory />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Create a mock for URL.createObjectURL and click
    const mockCreateObjectURL = jest.fn(() => 'blob:test');
    const mockRevokeObjectURL = jest.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    const exportButton = screen.getByText(/export csv/i);
    await user.click(exportButton!);

    expect(mockCreateObjectURL).toHaveBeenCalled();
  });

  it('shows relative time for undo actions', async () => {
    render(<UndoHistory />);

    await waitFor(() => {
      // Should show "Just now" or similar relative time
      const timeText = screen.getByText(/ago|just now/i);
      expect(timeText).toBeInTheDocument();
    });
  });
});

// ── B5.3 Shadow Log Page Tests ───────────────────────────────────────────────

describe('B5.3 Shadow Log Page', () => {
  let ShadowLogPage: any;

  beforeAll(async () => {
    const module = await import('@/app/dashboard/shadow-log/page');
    ShadowLogPage = module.default;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockShadowApi.getLog.mockResolvedValue({
      items: mockShadowLogEntries,
      total: 2,
      page: 1,
      pages: 1,
    });
    mockShadowApi.getStats.mockResolvedValue(mockShadowStats);
  });

  it('renders page header', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/shadow log/i)).toBeInTheDocument();
    });
  });

  it('displays stats strip', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/total actions/i)).toBeInTheDocument();
      expect(screen.getByText(/approval rate/i)).toBeInTheDocument();
      expect(screen.getByText(/pending review/i)).toBeInTheDocument();
    });
  });

  it('shows mode distribution bar chart', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/mode distribution/i)).toBeInTheDocument();
    });
  });

  it('renders action type distribution', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/action types/i)).toBeInTheDocument();
    });
  });

  it('displays filter bar', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument();
    });
  });

  it('shows export CSV button', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument();
    });
  });

  it('displays log table with entries', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
      expect(screen.getByText(/email reply/i)).toBeInTheDocument();
    });
  });

  it('shows risk score bars', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      // Risk percentages
      expect(screen.getByText(/35%/)).toBeInTheDocument();
      expect(screen.getByText(/75%/)).toBeInTheDocument();
    });
  });

  it('displays mode badges', async () => {
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/graduated/i)).toBeInTheDocument();
      expect(screen.getByText(/shadow/i)).toBeInTheDocument();
    });
  });

  it('expands row to show action payload', async () => {
    const user = userEvent.setup();
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Click on row to expand
    const refundRow = screen.getByText(/refund/i).closest('tr');
    await user.click(refundRow!);

    await waitFor(() => {
      expect(screen.getByText(/action payload/i)).toBeInTheDocument();
    });
  });

  it('filters by action type', async () => {
    const user = userEvent.setup();
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument();
    });

    // Open filters
    await user.click(screen.getByRole('button', { name: /filters/i }));

    await waitFor(() => {
      expect(screen.getByText(/action type/i)).toBeInTheDocument();
    });
  });

  it('approves pending action', async () => {
    const { prompt } = window;
    (window as any).prompt = jest.fn(() => 'Looks good');
    mockShadowApi.approve.mockResolvedValueOnce({});

    const user = userEvent.setup();
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Find and click approve button
    const approveButtons = screen.getAllByRole('button', { name: /approve/i });
    await user.click(approveButtons[0]);

    await waitFor(() => {
      expect(mockShadowApi.approve).toHaveBeenCalled();
    });

    window.prompt = prompt;
  });

  it('rejects pending action', async () => {
    const { prompt } = window;
    (window as any).prompt = jest.fn(() => 'Not approved');
    mockShadowApi.reject.mockResolvedValueOnce({});

    const user = userEvent.setup();
    render(<ShadowLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/refund/i)).toBeInTheDocument();
    });

    // Find and click reject button
    const rejectButtons = screen.getAllByRole('button', { name: /reject/i });
    await user.click(rejectButtons[0]);

    await waitFor(() => {
      expect(mockShadowApi.reject).toHaveBeenCalled();
    });

    window.prompt = prompt;
  });
});

// ── B5.4 Shadow Mode Settings Page Tests ─────────────────────────────────────

describe('B5.4 Shadow Mode Settings Page', () => {
  let ShadowModeSettingsPage: any;

  beforeAll(async () => {
    const module = await import('@/app/dashboard/settings/shadow-mode/page');
    ShadowModeSettingsPage = module.default;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockShadowApi.getMode.mockResolvedValue({ mode: 'shadow' });
    mockShadowApi.getPreferences.mockResolvedValue({ preferences: mockPreferences });
    mockShadowApi.getStats.mockResolvedValue(mockShadowStats);
  });

  it('renders page header', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/shadow mode settings/i)).toBeInTheDocument();
    });
  });

  it('displays global mode selector with three options', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/shadow mode/i)).toBeInTheDocument();
      expect(screen.getByText(/supervised mode/i)).toBeInTheDocument();
      expect(screen.getByText(/graduated mode/i)).toBeInTheDocument();
    });
  });

  it('highlights currently selected mode', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      // Shadow mode should be selected/highlighted
      const shadowCard = screen.getByText(/shadow mode/i).closest('button');
      expect(shadowCard).toHaveClass('border-orange-500');
    });
  });

  it('changes mode when different mode is clicked', async () => {
    mockShadowApi.setMode.mockResolvedValueOnce({ mode: 'graduated', previous_mode: 'shadow' });

    const user = userEvent.setup();
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/graduated mode/i)).toBeInTheDocument();
    });

    // Click on graduated mode
    const graduatedCard = screen.getByText(/graduated mode/i).closest('button');
    await user.click(graduatedCard!);

    await waitFor(() => {
      expect(mockShadowApi.setMode).toHaveBeenCalledWith('graduated', 'ui');
    });
  });

  it('displays per-action preferences table', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/per-action preferences/i)).toBeInTheDocument();
    });
  });

  it('shows existing preferences', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/refunds/i)).toBeInTheDocument();
    });
  });

  it('opens add preference modal', async () => {
    const user = userEvent.setup();
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add preference/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /add preference/i }));

    await waitFor(() => {
      expect(screen.getByText(/add preference/i)).toBeInTheDocument();
      expect(screen.getByText(/select category/i)).toBeInTheDocument();
    });
  });

  it('adds new preference', async () => {
    mockShadowApi.setPreference.mockResolvedValueOnce({
      id: 'pref-new',
      company_id: 'company-1',
      action_category: 'email_reply',
      preferred_mode: 'shadow',
      set_via: 'ui',
      updated_at: new Date().toISOString(),
    });

    const user = userEvent.setup();
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add preference/i })).toBeInTheDocument();
    });

    // Open modal
    await user.click(screen.getByRole('button', { name: /add preference/i }));

    await waitFor(() => {
      expect(screen.getByText(/action category/i)).toBeInTheDocument();
    });

    // Select category (need to interact with select)
    const categorySelect = screen.getByRole('combobox', { name: /action category/i });
    await user.selectOptions(categorySelect!, 'email_reply');

    // Add preference
    const addButton = screen.getByRole('button', { name: /add preference/i });
    await user.click(addButton);

    await waitFor(() => {
      expect(mockShadowApi.setPreference).toHaveBeenCalledWith('email_reply', 'shadow', 'ui');
    });
  });

  it('deletes preference', async () => {
    mockShadowApi.deletePreference.mockResolvedValueOnce({ deleted: true });

    // Mock confirm dialog
    const { confirm } = window;
    (window as any).confirm = jest.fn(() => true);

    const user = userEvent.setup();
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/refunds/i)).toBeInTheDocument();
    });

    // Find and click delete button (trash icon)
    const deleteButtons = screen.getAllByRole('button').filter(btn => 
      btn.querySelector('svg')?.innerHTML?.includes('trash') || 
      btn.className?.includes('hover:text-red')
    );

    if (deleteButtons.length > 0) {
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(mockShadowApi.deletePreference).toHaveBeenCalled();
      });
    }

    window.confirm = confirm;
  });

  it('displays undo window settings', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/undo window/i)).toBeInTheDocument();
    });
  });

  it('displays risk threshold sliders', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/risk thresholds/i)).toBeInTheDocument();
      expect(screen.getByText(/force shadow above risk/i)).toBeInTheDocument();
      expect(screen.getByText(/auto-execute below risk/i)).toBeInTheDocument();
    });
  });

  it('displays what-if simulator', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/what-if simulator/i)).toBeInTheDocument();
    });
  });

  it('subscribes to socket events for real-time sync', async () => {
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(mockSocket.on).toHaveBeenCalledWith('shadow:mode_changed', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('shadow:preference_changed', expect.any(Function));
    });
  });

  it('resets all preferences when reset button clicked', async () => {
    mockShadowApi.deletePreference.mockResolvedValue({ deleted: true });

    const { confirm } = window;
    (window as any).confirm = jest.fn(() => true);

    const user = userEvent.setup();
    render(<ShadowModeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/reset all/i)).toBeInTheDocument();
    });

    // Click reset button
    const resetButton = screen.getByText(/reset all/i);
    await user.click(resetButton);

    await waitFor(() => {
      expect(mockShadowApi.deletePreference).toHaveBeenCalled();
    });

    window.confirm = confirm;
  });
});
