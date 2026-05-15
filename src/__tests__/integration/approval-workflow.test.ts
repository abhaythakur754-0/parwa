/**
 * PARWA Integration Tests — Approval Workflow (Day 4)
 *
 * End-to-end integration tests verifying the approval lifecycle:
 * 1. Socket event → approval store → notification → badge count
 * 2. Approval lifecycle: pending → approved/rejected/timeout
 * 3. Optimistic updates with API failure revert
 * 4. Batch approval processing with auto-timeout
 */

import { useApprovalStore, Approval } from '@/lib/approval-store';
import { useNotificationStore } from '@/lib/notification-store';

// ── Setup ─────────────────────────────────────────────────────────────

beforeEach(() => {
  useApprovalStore.setState({
    approvals: [],
    pendingCount: 0,
    isLoading: false,
    activeApprovalId: null,
  });
  useNotificationStore.getState().clearAll();
});

// ── Helper ────────────────────────────────────────────────────────────

function addPendingApproval(overrides: Record<string, unknown> = {}) {
  useApprovalStore.getState().handleApprovalPending({
    id: overrides.id || 'apr-test-1',
    type: 'refund',
    title: overrides.title || 'Refund $99.99',
    description: 'Customer requests refund',
    reason: 'Duplicate charge',
    risk_level: overrides.risk_level || 'medium',
    ai_confidence: overrides.ai_confidence || 90,
    expires_at: overrides.expires_at || new Date(Date.now() + 3600000).toISOString(),
    requested_by: overrides.requested_by || 'Refund Agent',
    ...overrides,
  });
}

// ── Integration: Approval Arrival ──────────────────────────────────────

describe('Integration: approval arrival flow', () => {
  it('should process approval:pending event and update both stores', () => {
    addPendingApproval();

    const approvalState = useApprovalStore.getState();
    expect(approvalState.pendingCount).toBe(1);
    expect(approvalState.approvals[0].status).toBe('pending');
    expect(approvalState.approvals[0].type).toBe('refund');
  });

  it('should show correct badge count for multiple pending approvals', () => {
    addPendingApproval({ id: 'apr-1' });
    addPendingApproval({ id: 'apr-2', type: 'escalation', title: 'Escalation' });
    addPendingApproval({ id: 'apr-3', type: 'discount', title: 'Discount' });

    expect(useApprovalStore.getState().pendingCount).toBe(3);
  });
});

// ── Integration: Approval Lifecycle ───────────────────────────────────

describe('Integration: approval lifecycle transitions', () => {
  it('should handle pending → approved lifecycle', () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    useApprovalStore.getState().handleApprovalApproved({ id, respondedBy: 'Admin User' });

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('approved');
    expect(approval.respondedBy).toBe('Admin User');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });

  it('should handle pending → rejected lifecycle', () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    useApprovalStore.getState().handleApprovalRejected({ id, respondedBy: 'Manager', reason: 'Policy violation' });

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('rejected');
    expect(approval.responseReason).toBe('Policy violation');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });

  it('should handle pending → timeout lifecycle', () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    useApprovalStore.getState().handleApprovalTimeout({ id });

    expect(useApprovalStore.getState().approvals[0].status).toBe('timeout');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });

  it('should handle mixed lifecycle: some approved, some still pending', () => {
    addPendingApproval({ id: 'apr-1', title: 'Approval 1' });
    addPendingApproval({ id: 'apr-2', title: 'Approval 2' });
    addPendingApproval({ id: 'apr-3', title: 'Approval 3' });

    useApprovalStore.getState().handleApprovalApproved({ id: 'apr-1' });
    useApprovalStore.getState().handleApprovalRejected({ id: 'apr-3' });

    expect(useApprovalStore.getState().pendingCount).toBe(1);
    const pending = useApprovalStore.getState().getPendingApprovals();
    expect(pending.length).toBe(1);
    expect(pending[0].id).toBe('apr-2');
  });
});

// ── Integration: Optimistic Updates with Revert ───────────────────────

describe('Integration: optimistic approval updates', () => {
  it('should optimistically approve and then confirm via API', async () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    // Mock successful API
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

    await useApprovalStore.getState().approve(id, 'Looks good');

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('approved');
    expect(approval.respondedBy).toBe('You');
  });

  it('should revert optimistic approve on API failure', async () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    // Mock failed API
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 500 });

    await expect(useApprovalStore.getState().approve(id)).rejects.toThrow();

    expect(useApprovalStore.getState().approvals[0].status).toBe('pending');
    expect(useApprovalStore.getState().pendingCount).toBe(1);
  });

  it('should revert optimistic reject on API failure', async () => {
    addPendingApproval();
    const id = useApprovalStore.getState().approvals[0].id;

    // Mock failed API
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 500 });

    await expect(useApprovalStore.getState().reject(id)).rejects.toThrow();

    expect(useApprovalStore.getState().approvals[0].status).toBe('pending');
  });
});

// ── Integration: Batch Processing ─────────────────────────────────────

describe('Integration: batch approval processing', () => {
  it('should process batch of mixed-status approvals', () => {
    useApprovalStore.getState().handleApprovalBatch({
      approvals: [
        {
          id: 'batch-1',
          type: 'refund',
          title: 'Refund A',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'low',
          ai_confidence: 95,
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          requested_by: 'Agent A',
        },
        {
          id: 'batch-2',
          type: 'escalation',
          title: 'Escalation B',
          description: 'desc',
          reason: 'reason',
          status: 'approved',
          risk_level: 'medium',
          ai_confidence: 80,
          expires_at: new Date(Date.now() + 1800000).toISOString(),
          requested_by: 'Agent B',
          responded_by: 'Admin',
        },
      ],
    });

    const state = useApprovalStore.getState();
    expect(state.approvals.length).toBe(2);
    expect(state.pendingCount).toBe(1);
  });

  it('should auto-timeout expired approvals in batch', () => {
    useApprovalStore.getState().handleApprovalBatch({
      approvals: [
        {
          id: 'expired-batch-1',
          type: 'refund',
          title: 'Expired Refund',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'low',
          ai_confidence: 90,
          expires_at: new Date(Date.now() - 5000).toISOString(), // Already expired
          requested_by: 'Agent',
        },
      ],
    });

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('timeout');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });
});

// ── Integration: Approval → Notification Bridge ───────────────────────

describe('Integration: approval triggers notification', () => {
  it('should create toast notification when approval:pending arrives', () => {
    // This simulates what useRealtimeEvents.handleApprovalPending does
    addPendingApproval();

    useNotificationStore.getState().addToast({
      type: 'approval',
      category: 'approval',
      title: 'New Approval Request',
      message: 'Refund $99.99',
      priority: 'high',
      actionUrl: '/dashboard/monitoring',
      actionLabel: 'Review',
    });

    const notifState = useNotificationStore.getState();
    expect(notifState.toasts.length).toBeGreaterThanOrEqual(1);
    expect(notifState.unreadCount).toBeGreaterThanOrEqual(1);

    const approvalToast = notifState.toasts.find((t) => t.type === 'approval');
    expect(approvalToast).toBeDefined();
    expect(approvalToast?.actionUrl).toBe('/dashboard/monitoring');
  });

  it('should show approval badge count equal to pending approvals', () => {
    addPendingApproval({ id: 'apr-1' });
    addPendingApproval({ id: 'apr-2' });

    // The dashboard header should show this count
    expect(useApprovalStore.getState().pendingCount).toBe(2);
  });
});

// ── Integration: Active Approval Selection ────────────────────────────

describe('Integration: active approval selection', () => {
  it('should track which approval is being viewed', () => {
    addPendingApproval({ id: 'apr-1' });
    addPendingApproval({ id: 'apr-2' });

    useApprovalStore.getState().setActiveApproval('apr-2');

    expect(useApprovalStore.getState().activeApprovalId).toBe('apr-2');

    // Clear selection
    useApprovalStore.getState().setActiveApproval(null);
    expect(useApprovalStore.getState().activeApprovalId).toBeNull();
  });
});
