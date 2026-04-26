/**
 * JARVIS Approval Workflow (Week 3 - Phase 1)
 *
 * Manages approval workflow for high-risk operations.
 * Handles approval requests, multi-level approvals, and expiration.
 */

import type {
  Draft,
  ApprovalRequest,
  ApprovalRecord,
  ApprovalStatus,
} from '@/types/command';

// ── Approval Store ────────────────────────────────────────────────────

interface ApprovalStore {
  requests: Map<string, ApprovalRequest>;
  userApprovals: Map<string, Set<string>>; // user_id -> set of approval_ids
}

// ── Approval Workflow Class ───────────────────────────────────────────

export class ApprovalWorkflow {
  private store: ApprovalStore;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor() {
    this.store = {
      requests: new Map(),
      userApprovals: new Map(),
    };
    this.startCleanupInterval();
  }

  /**
   * Create approval request from draft
   */
  createApprovalRequest(
    draft: Draft,
    requestedBy: string,
    options: {
      approver_roles?: string[];
      approver_ids?: string[];
      priority?: 'low' | 'medium' | 'high' | 'urgent';
      reason?: string;
    } = {}
  ): ApprovalRequest {
    const expiryHours = this.getApprovalExpiryHours(draft);

    const request: ApprovalRequest = {
      id: this.generateApprovalId(),
      draft_id: draft.id,
      command_id: draft.command_id,
      tenant_id: draft.tenant_id,
      requested_by: requestedBy,
      approver_roles: options.approver_roles || ['manager', 'admin'],
      approver_ids: options.approver_ids,
      status: 'pending',
      priority: options.priority || 'medium',
      reason: options.reason || this.generateReason(draft),
      created_at: new Date(),
      expires_at: new Date(Date.now() + expiryHours * 60 * 60 * 1000),
      approvals: [],
      rejections: [],
      min_approvals: this.getMinApprovals(draft.action.risk_level),
      current_approvals: 0,
      metadata: {
        action_type: draft.action.type,
        risk_level: draft.action.risk_level,
      },
    };

    this.store.requests.set(request.id, request);
    return request;
  }

  /**
   * Get approval request by ID
   */
  getApprovalRequest(approvalId: string): ApprovalRequest | undefined {
    return this.store.requests.get(approvalId);
  }

  /**
   * Get approval request by draft ID
   */
  getApprovalByDraft(draftId: string): ApprovalRequest | undefined {
    for (const request of this.store.requests.values()) {
      if (request.draft_id === draftId) {
        return request;
      }
    }
    return undefined;
  }

  /**
   * Get pending approvals for user
   */
  getPendingApprovalsForUser(
    userId: string,
    userRole: string,
    tenantId: string
  ): ApprovalRequest[] {
    const userApprovalIds = this.store.userApprovals.get(userId) || new Set();

    return Array.from(this.store.requests.values())
      .filter((r) =>
        r.tenant_id === tenantId &&
        r.status === 'pending' &&
        !this.isExpired(r) &&
        (userApprovalIds.has(r.id) ||
          r.approver_roles?.includes(userRole) ||
          r.approver_ids?.includes(userId))
      )
      .sort((a, b) => {
        const priorityOrder = { urgent: 0, high: 1, medium: 2, low: 3 };
        return priorityOrder[a.priority] - priorityOrder[b.priority];
      });
  }

  /**
   * Get all pending approvals for tenant
   */
  getPendingApprovals(tenantId: string): ApprovalRequest[] {
    return Array.from(this.store.requests.values())
      .filter((r) => r.tenant_id === tenantId && r.status === 'pending' && !this.isExpired(r));
  }

  /**
   * Approve request
   */
  approve(
    approvalId: string,
    approverId: string,
    approverName: string,
    comment?: string
  ): ApprovalRequest | null {
    const request = this.store.requests.get(approvalId);
    if (!request || request.status !== 'pending') return null;

    if (this.isExpired(request)) {
      request.status = 'expired';
      return request;
    }

    // Check if already approved by this user
    if (request.approvals.some((a) => a.approver_id === approverId)) {
      return null;
    }

    // Add approval
    const record: ApprovalRecord = {
      approver_id: approverId,
      approver_name: approverName,
      action: 'approved',
      timestamp: new Date(),
      comment,
    };

    request.approvals.push(record);
    request.current_approvals++;

    // Check if minimum approvals reached
    if (request.current_approvals >= request.min_approvals) {
      request.status = 'approved';
    }

    return request;
  }

  /**
   * Reject request
   */
  reject(
    approvalId: string,
    rejecterId: string,
    rejecterName: string,
    reason: string
  ): ApprovalRequest | null {
    const request = this.store.requests.get(approvalId);
    if (!request || request.status !== 'pending') return null;

    // Add rejection
    const record: ApprovalRecord = {
      approver_id: rejecterId,
      approver_name: rejecterName,
      action: 'rejected',
      timestamp: new Date(),
      comment: reason,
    };

    request.rejections.push(record);
    request.status = 'rejected';

    return request;
  }

  /**
   * Check if user can approve
   */
  canUserApprove(
    approvalId: string,
    userId: string,
    userRole: string
  ): boolean {
    const request = this.store.requests.get(approvalId);
    if (!request || request.status !== 'pending') return false;

    // Check if already approved
    if (request.approvals.some((a) => a.approver_id === userId)) {
      return false;
    }

    // Check role or explicit ID
    return (
      request.approver_roles?.includes(userRole) ||
      request.approver_ids?.includes(userId) ||
      false
    );
  }

  /**
   * Get approval statistics
   */
  getStats(tenantId?: string): {
    total: number;
    pending: number;
    approved: number;
    rejected: number;
    expired: number;
  } {
    let requests = Array.from(this.store.requests.values());
    if (tenantId) {
      requests = requests.filter((r) => r.tenant_id === tenantId);
    }

    return {
      total: requests.length,
      pending: requests.filter((r) => r.status === 'pending').length,
      approved: requests.filter((r) => r.status === 'approved').length,
      rejected: requests.filter((r) => r.status === 'rejected').length,
      expired: requests.filter((r) => r.status === 'expired').length,
    };
  }

  /**
   * Cancel approval request
   */
  cancelApproval(approvalId: string, cancelledBy: string): boolean {
    const request = this.store.requests.get(approvalId);
    if (!request || request.status !== 'pending') return false;

    request.status = 'rejected';
    request.metadata.cancelled_by = cancelledBy;
    request.metadata.cancelled_at = new Date().toISOString();

    return true;
  }

  /**
   * Shutdown
   */
  shutdown(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.store.requests.clear();
    this.store.userApprovals.clear();
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Get approval expiry hours
   */
  private getApprovalExpiryHours(draft: Draft): number {
    const hours: Record<string, number> = {
      mini_parwa: 4,
      parwa: 24,
      parwa_high: 48,
    };
    return hours[draft.tenant_id] || 24;
  }

  /**
   * Get minimum approvals required
   */
  private getMinApprovals(riskLevel: string): number {
    const minApprovals: Record<string, number> = {
      low: 1,
      medium: 1,
      high: 2,
      critical: 2,
    };
    return minApprovals[riskLevel] || 1;
  }

  /**
   * Generate reason from draft
   */
  private generateReason(draft: Draft): string {
    return `Approval required for: ${draft.preview.title}. ${draft.preview.description}`;
  }

  /**
   * Check if request is expired
   */
  private isExpired(request: ApprovalRequest): boolean {
    return new Date() > request.expires_at;
  }

  /**
   * Generate approval ID
   */
  private generateApprovalId(): string {
    return `apr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Start cleanup interval
   */
  private startCleanupInterval(): void {
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpired();
    }, 60 * 60 * 1000); // Every hour
  }

  /**
   * Cleanup expired requests
   */
  private cleanupExpired(): void {
    for (const [id, request] of this.store.requests) {
      if (this.isExpired(request) && request.status === 'pending') {
        request.status = 'expired';
      }
    }
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createApprovalWorkflow(): ApprovalWorkflow {
  return new ApprovalWorkflow();
}
