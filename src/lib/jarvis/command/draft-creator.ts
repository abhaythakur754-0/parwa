/**
 * JARVIS Draft Creator (Week 3 - Phase 1)
 *
 * Creates drafts for high-risk operations requiring approval.
 * Handles preview generation, expiration, and draft management.
 */

import type {
  Command,
  CommandAction,
  Draft,
  DraftPreview,
  DraftChange,
  AffectedItem,
  CommandResult,
} from '@/types/command';

// ── Draft Store ───────────────────────────────────────────────────────

interface DraftStore {
  drafts: Map<string, Draft>;
  maxDraftsPerTenant: number;
}

// ── Draft Creator Class ───────────────────────────────────────────────

export class DraftCreator {
  private store: DraftStore;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor() {
    this.store = {
      drafts: new Map(),
      maxDraftsPerTenant: 100,
    };
    this.startCleanupInterval();
  }

  /**
   * Create a draft from command
   */
  async createDraft(command: Command): Promise<Draft> {
    const preview = await this.generatePreview(command);
    const expiryHours = this.getExpiryHours(command.variant);

    const draft: Draft = {
      id: this.generateDraftId(),
      command_id: command.id,
      tenant_id: command.tenant_id,
      session_id: command.session_id,
      action: command.action,
      preview,
      status: 'pending',
      created_at: new Date(),
      expires_at: new Date(Date.now() + expiryHours * 60 * 60 * 1000),
    };

    this.store.drafts.set(draft.id, draft);
    return draft;
  }

  /**
   * Get draft by ID
   */
  getDraft(draftId: string): Draft | undefined {
    return this.store.drafts.get(draftId);
  }

  /**
   * Get drafts by session
   */
  getDraftsBySession(sessionId: string): Draft[] {
    return Array.from(this.store.drafts.values())
      .filter((d) => d.session_id === sessionId && d.status === 'pending');
  }

  /**
   * Get drafts by tenant
   */
  getDraftsByTenant(tenantId: string): Draft[] {
    return Array.from(this.store.drafts.values())
      .filter((d) => d.tenant_id === tenantId && d.status === 'pending');
  }

  /**
   * Approve draft
   */
  async approveDraft(draftId: string, approvedBy: string): Promise<Draft | null> {
    const draft = this.store.drafts.get(draftId);
    if (!draft || draft.status !== 'pending') return null;

    if (this.isExpired(draft)) {
      draft.status = 'expired';
      return draft;
    }

    draft.status = 'approved';
    draft.approved_by = approvedBy;
    draft.approved_at = new Date();

    return draft;
  }

  /**
   * Reject draft
   */
  rejectDraft(draftId: string, rejectedBy: string, reason: string): Draft | null {
    const draft = this.store.drafts.get(draftId);
    if (!draft || draft.status !== 'pending') return null;

    draft.status = 'rejected';
    draft.rejection_reason = reason;

    return draft;
  }

  /**
   * Mark draft as executed
   */
  markExecuted(draftId: string, result: CommandResult): Draft | null {
    const draft = this.store.drafts.get(draftId);
    if (!draft) return null;

    draft.status = 'executed';
    draft.execution_result = result;

    return draft;
  }

  /**
   * Cancel draft
   */
  cancelDraft(draftId: string): boolean {
    const draft = this.store.drafts.get(draftId);
    if (!draft || draft.status !== 'pending') return false;

    this.store.drafts.delete(draftId);
    return true;
  }

  /**
   * Get pending drafts count
   */
  getPendingDraftsCount(tenantId?: string): number {
    let drafts = Array.from(this.store.drafts.values()).filter((d) => d.status === 'pending');
    if (tenantId) {
      drafts = drafts.filter((d) => d.tenant_id === tenantId);
    }
    return drafts.length;
  }

  /**
   * Shutdown
   */
  shutdown(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.store.drafts.clear();
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Generate preview for draft
   */
  private async generatePreview(command: Command): Promise<DraftPreview> {
    const action = command.action;
    const params = action.params;

    const preview: DraftPreview = {
      title: this.generateTitle(action),
      description: this.generateDescription(action, params),
      changes: [],
      affected_items: [],
      warnings: [],
      estimated_impact: this.getEstimatedImpact(action.risk_level),
    };

    // Generate changes based on action type
    preview.changes = this.generateChanges(action, params);

    // Generate affected items
    preview.affected_items = this.generateAffectedItems(action, params);

    // Add warnings for high-risk actions
    if (action.risk_level === 'high' || action.risk_level === 'critical') {
      preview.warnings.push(
        'This action may have significant impact. Please review carefully before approving.'
      );
    }

    if (!action.reversible) {
      preview.warnings.push(
        'This action cannot be undone. Once approved, it will be permanently applied.'
      );
    }

    return preview;
  }

  /**
   * Generate title for action
   */
  private generateTitle(action: CommandAction): string {
    const titles: Record<string, string> = {
      escalate_ticket: 'Escalate Ticket',
      merge_tickets: 'Merge Tickets',
      export_data: 'Export Data',
      create_rule: 'Create Automation Rule',
      update_rule: 'Update Automation Rule',
    };
    return titles[action.type] || `Execute: ${action.type.replace(/_/g, ' ')}`;
  }

  /**
   * Generate description for action
   */
  private generateDescription(action: CommandAction, params: Record<string, unknown>): string {
    switch (action.type) {
      case 'escalate_ticket':
        return `Escalate ticket ${params.ticket_id || 'to higher level support'}`;
      case 'merge_tickets':
        return `Merge ${Array.isArray(params.ticket_ids) ? params.ticket_ids.length : 'multiple'} tickets into primary ticket`;
      case 'export_data':
        return `Export ${params.data_type || 'data'} as ${params.format || 'CSV'}`;
      default:
        return `Execute ${action.type.replace(/_/g, ' ')}`;
    }
  }

  /**
   * Generate changes list
   */
  private generateChanges(action: CommandAction, params: Record<string, unknown>): DraftChange[] {
    const changes: DraftChange[] = [];

    switch (action.type) {
      case 'escalate_ticket':
        changes.push({
          field: 'status',
          current_value: 'current',
          new_value: 'escalated',
          description: 'Ticket status will be changed to escalated',
        });
        if (params.reason) {
          changes.push({
            field: 'escalation_reason',
            current_value: null,
            new_value: params.reason,
            description: 'Escalation reason will be recorded',
          });
        }
        break;

      case 'merge_tickets':
        if (Array.isArray(params.ticket_ids)) {
          changes.push({
            field: 'merged_tickets',
            current_value: params.ticket_ids.join(', '),
            new_value: params.primary_ticket_id,
            description: `${params.ticket_ids.length - 1} tickets will be merged`,
          });
        }
        break;

      case 'export_data':
        changes.push({
          field: 'export_type',
          current_value: null,
          new_value: params.data_type,
          description: `Data type: ${params.data_type}`,
        });
        if (params.date_from || params.date_to) {
          changes.push({
            field: 'date_range',
            current_value: null,
            new_value: `${params.date_from || 'beginning'} to ${params.date_to || 'now'}`,
            description: 'Export date range',
          });
        }
        break;

      default:
        for (const [key, value] of Object.entries(params)) {
          changes.push({
            field: key,
            current_value: 'current',
            new_value: value,
            description: `${key} will be updated`,
          });
        }
    }

    return changes;
  }

  /**
   * Generate affected items list
   */
  private generateAffectedItems(action: CommandAction, params: Record<string, unknown>): AffectedItem[] {
    const items: AffectedItem[] = [];

    if (params.ticket_id) {
      items.push({
        type: 'ticket',
        id: params.ticket_id as string,
      });
    }

    if (Array.isArray(params.ticket_ids)) {
      for (const id of params.ticket_ids) {
        items.push({
          type: 'ticket',
          id: id as string,
        });
      }
    }

    if (params.customer_id) {
      items.push({
        type: 'customer',
        id: params.customer_id as string,
      });
    }

    return items;
  }

  /**
   * Get estimated impact from risk level
   */
  private getEstimatedImpact(riskLevel: string): 'low' | 'medium' | 'high' {
    const impactMap: Record<string, 'low' | 'medium' | 'high'> = {
      low: 'low',
      medium: 'medium',
      high: 'high',
      critical: 'high',
    };
    return impactMap[riskLevel] || 'medium';
  }

  /**
   * Get expiry hours based on variant
   */
  private getExpiryHours(variant: string): number {
    const hours: Record<string, number> = {
      mini_parwa: 1,
      parwa: 4,
      parwa_high: 24,
    };
    return hours[variant] || 4;
  }

  /**
   * Check if draft is expired
   */
  private isExpired(draft: Draft): boolean {
    return new Date() > draft.expires_at;
  }

  /**
   * Generate draft ID
   */
  private generateDraftId(): string {
    return `draft_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
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
   * Cleanup expired drafts
   */
  private cleanupExpired(): void {
    for (const [id, draft] of this.store.drafts) {
      if (this.isExpired(draft)) {
        draft.status = 'expired';
        // Optionally delete: this.store.drafts.delete(id);
      }
    }
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createDraftCreator(): DraftCreator {
  return new DraftCreator();
}
