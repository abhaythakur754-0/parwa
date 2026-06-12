/**
 * PARWA Approval Store — Unit Tests (Day 4)
 *
 * Tests approval lifecycle: add, approve, reject, timeout, batch.
 * Covers Socket.io event handlers, API integration, and computed values.
 */

import { useApprovalStore } from '@/lib/approval-store';

// ── Setup ─────────────────────────────────────────────────────────────

beforeEach(() => {
  // Reset store state
  const store = useApprovalStore.getState();
  useApprovalStore.setState({
    approvals: [],
    pendingCount: 0,
    isLoading: false,
    activeApprovalId: null,
  });
});

// ── Helper to create a base approval ──────────────────────────────────

function createBaseApproval(overrides: Record<string, unknown> = {}) {
  return {
    type: 'refund' as const,
    title: 'Refund $149.99',
    description: 'Customer requests refund for duplicate charge',
    requestedBy: 'FAQ Agent',
    ticketId: 'tkt-001',
    ticketNumber: 'TKT-0001',
    customerName: 'Sarah Mitchell',
    amount: 149.99,
    currency: 'USD',
    reason: 'Duplicate charge on Jan 15th',
    riskLevel: 'medium' as const,
    aiConfidence: 92.5,
    expiresAt: new Date(Date.now() + 3600000).toISOString(),
    ...overrides,
  };
}

// ── addApproval ───────────────────────────────────────────────────────

describe('approval-store: addApproval', () => {
  it('should add a pending approval with generated id and createdAt', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const approvals = useApprovalStore.getState().approvals;
    expect(approvals.length).toBe(1);
    expect(approvals[0].status).toBe('pending');
    expect(approvals[0].id).toBeDefined();
    expect(approvals[0].createdAt).toBeDefined();
    expect(useApprovalStore.getState().pendingCount).toBe(1);
  });

  it('should increment pendingCount for each new approval', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval({ title: 'A' }));
    store.addApproval(createBaseApproval({ title: 'B' }));

    expect(useApprovalStore.getState().pendingCount).toBe(2);
  });
});

// ── approve (optimistic update) ───────────────────────────────────────

describe('approval-store: approve', () => {
  it('should optimistically update approval to approved', async () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const id = useApprovalStore.getState().approvals[0].id;

    // Mock successful API response
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

    await store.approve(id, 'Looks good');

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('approved');
    expect(approval.respondedBy).toBe('You');
    expect(approval.responseReason).toBe('Looks good');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });

  it('should revert to pending on API failure', async () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const id = useApprovalStore.getState().approvals[0].id;

    // Mock failed API response
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 500 });

    await expect(store.approve(id)).rejects.toThrow();

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('pending');
    expect(useApprovalStore.getState().pendingCount).toBe(1);
  });
});

// ── reject (optimistic update) ────────────────────────────────────────

describe('approval-store: reject', () => {
  it('should optimistically update approval to rejected', async () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const id = useApprovalStore.getState().approvals[0].id;

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

    await store.reject(id, 'Insufficient evidence');

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('rejected');
    expect(approval.respondedBy).toBe('You');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });

  it('should revert to pending on API failure', async () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const id = useApprovalStore.getState().approvals[0].id;

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 500 });

    await expect(store.reject(id)).rejects.toThrow();

    expect(useApprovalStore.getState().approvals[0].status).toBe('pending');
  });
});

// ── handleApprovalPending (Socket.io handler) ─────────────────────────

describe('approval-store: handleApprovalPending', () => {
  it('should add approval from socket event data', () => {
    const store = useApprovalStore.getState();
    store.handleApprovalPending({
      id: 'approval-1',
      type: 'refund',
      title: 'Refund $89.99',
      description: 'Customer wants refund',
      requested_by: 'Refund Agent',
      reason: 'Defective product',
      risk_level: 'low',
      ai_confidence: 95.2,
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    });

    expect(useApprovalStore.getState().approvals.length).toBe(1);
    expect(useApprovalStore.getState().pendingCount).toBe(1);
  });

  it('should not add duplicate approval by id', () => {
    const store = useApprovalStore.getState();
    store.handleApprovalPending({
      id: 'approval-1',
      type: 'refund',
      title: 'Refund',
      description: 'desc',
      reason: 'reason',
      risk_level: 'low',
      ai_confidence: 90,
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    });

    store.handleApprovalPending({
      id: 'approval-1', // Same id
      type: 'refund',
      title: 'Refund',
      description: 'desc',
      reason: 'reason',
      risk_level: 'low',
      ai_confidence: 90,
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    });

    expect(useApprovalStore.getState().approvals.length).toBe(1);
  });
});

// ── handleApprovalApproved (Socket.io handler) ────────────────────────

describe('approval-store: handleApprovalApproved', () => {
  it('should update approval status to approved via socket event', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());
    const id = useApprovalStore.getState().approvals[0].id;

    store.handleApprovalApproved({ id, respondedBy: 'Admin', reason: 'Approved' });

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('approved');
    expect(approval.respondedBy).toBe('Admin');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });
});

// ── handleApprovalRejected (Socket.io handler) ────────────────────────

describe('approval-store: handleApprovalRejected', () => {
  it('should update approval status to rejected via socket event', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());
    const id = useApprovalStore.getState().approvals[0].id;

    store.handleApprovalRejected({ id, respondedBy: 'Admin', reason: 'Not authorized' });

    expect(useApprovalStore.getState().approvals[0].status).toBe('rejected');
  });
});

// ── handleApprovalTimeout (Socket.io handler) ─────────────────────────

describe('approval-store: handleApprovalTimeout', () => {
  it('should update approval status to timeout via socket event', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());
    const id = useApprovalStore.getState().approvals[0].id;

    store.handleApprovalTimeout({ id });

    expect(useApprovalStore.getState().approvals[0].status).toBe('timeout');
    expect(useApprovalStore.getState().pendingCount).toBe(0);
  });
});

// ── handleApprovalBatch (Socket.io handler) ───────────────────────────

describe('approval-store: handleApprovalBatch', () => {
  it('should merge batch approvals', () => {
    const store = useApprovalStore.getState();
    store.handleApprovalBatch({
      approvals: [
        {
          id: 'batch-1',
          type: 'refund',
          title: 'Refund A',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'low',
          ai_confidence: 90,
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          requested_by: 'Agent 1',
        },
        {
          id: 'batch-2',
          type: 'escalation',
          title: 'Escalation B',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'high',
          ai_confidence: 60,
          expires_at: new Date(Date.now() + 1800000).toISOString(),
          requested_by: 'Agent 2',
        },
      ],
    });

    expect(useApprovalStore.getState().approvals.length).toBe(2);
  });

  it('should auto-timeout expired pending approvals in batch', () => {
    const store = useApprovalStore.getState();
    store.handleApprovalBatch({
      approvals: [
        {
          id: 'expired-1',
          type: 'refund',
          title: 'Expired Refund',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'low',
          ai_confidence: 90,
          expires_at: new Date(Date.now() - 1000).toISOString(), // Already expired
          requested_by: 'Agent',
        },
      ],
    });

    const approval = useApprovalStore.getState().approvals[0];
    expect(approval.status).toBe('timeout');
  });
});

// ── Computed: getPendingApprovals ─────────────────────────────────────

describe('approval-store: getPendingApprovals', () => {
  it('should return only pending approvals', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval({ title: 'A' }));
    store.addApproval(createBaseApproval({ title: 'B' }));

    // Approve one — re-read state after mutations
    const id = useApprovalStore.getState().approvals[0].id;
    useApprovalStore.getState().handleApprovalApproved({ id });

    const pending = useApprovalStore.getState().getPendingApprovals();
    expect(pending.length).toBe(1);
    // The remaining pending could be either A or B depending on order
    expect(pending[0].title).toBeDefined();
  });
});

// ── Computed: getApprovalById ─────────────────────────────────────────

describe('approval-store: getApprovalById', () => {
  it('should find approval by id', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval());

    const id = useApprovalStore.getState().approvals[0].id;
    const found = store.getApprovalById(id);
    expect(found).toBeDefined();
    expect(found?.id).toBe(id);
  });

  it('should return undefined for non-existent id', () => {
    expect(useApprovalStore.getState().getApprovalById('nonexistent')).toBeUndefined();
  });
});

// ── Computed: isExpired ───────────────────────────────────────────────

describe('approval-store: isExpired', () => {
  it('should detect expired approval', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval({
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    }));

    const id = useApprovalStore.getState().approvals[0].id;
    expect(store.isExpired(id)).toBe(true);
  });

  it('should not flag non-expired approval', () => {
    const store = useApprovalStore.getState();
    store.addApproval(createBaseApproval({
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    }));

    const id = useApprovalStore.getState().approvals[0].id;
    expect(store.isExpired(id)).toBe(false);
  });
});

// ── setActiveApproval ─────────────────────────────────────────────────

describe('approval-store: setActiveApproval', () => {
  it('should set active approval id', () => {
    const store = useApprovalStore.getState();
    store.setActiveApproval('approval-123');
    expect(useApprovalStore.getState().activeApprovalId).toBe('approval-123');
  });

  it('should clear active approval id with null', () => {
    const store = useApprovalStore.getState();
    store.setActiveApproval('approval-123');
    store.setActiveApproval(null);
    expect(useApprovalStore.getState().activeApprovalId).toBeNull();
  });
});

// ── fetchApprovals (API) ──────────────────────────────────────────────

describe('approval-store: fetchApprovals', () => {
  it('should handle 404 gracefully', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 404 });

    await useApprovalStore.getState().fetchApprovals();

    expect(useApprovalStore.getState().approvals.length).toBe(0);
    expect(useApprovalStore.getState().isLoading).toBe(false);
  });

  it('should parse and set approvals from API', async () => {
    const mockData = {
      approvals: [
        {
          id: 'api-1',
          type: 'refund',
          title: 'API Refund',
          description: 'desc',
          reason: 'reason',
          status: 'pending',
          risk_level: 'low',
          ai_confidence: 90,
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          requested_by: 'Agent',
        },
      ],
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    await useApprovalStore.getState().fetchApprovals();

    expect(useApprovalStore.getState().approvals.length).toBe(1);
    expect(useApprovalStore.getState().approvals[0].id).toBe('api-1');
  });
});
