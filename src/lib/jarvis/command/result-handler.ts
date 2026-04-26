/**
 * JARVIS Result Handler (Week 3 - Phase 1)
 *
 * Handles command execution results, formatting, and side effects.
 */

import type {
  Command,
  CommandResult,
  CommandError,
  ExecutionMode,
} from '@/types/command';

// ── Result Formatter Types ────────────────────────────────────────────

export interface FormattedResult {
  success: boolean;
  message: string;
  data?: unknown;
  actions?: ResultAction[];
  undo_available: boolean;
  next_suggestions?: string[];
}

export interface ResultAction {
  id: string;
  label: string;
  command: string;
  type: 'primary' | 'secondary';
}

// ── Result Handler Class ──────────────────────────────────────────────

export class ResultHandler {
  private resultHistory: Map<string, CommandResult[]> = new Map();

  /**
   * Handle successful result
   */
  handleSuccess(command: Command, result: CommandResult): FormattedResult {
    // Store in history
    this.addToHistory(command.session_id, result);

    return {
      success: true,
      message: result.message || this.generateSuccessMessage(command),
      data: result.data,
      actions: this.generateActions(command, result),
      undo_available: result.undo_available,
      next_suggestions: this.generateSuggestions(command),
    };
  }

  /**
   * Handle error result
   */
  handleError(command: Command, error: CommandError): FormattedResult {
    return {
      success: false,
      message: error.message,
      data: {
        error_code: error.code,
        details: error.details,
        recoverable: error.recoverable,
        suggested_fix: error.suggested_fix,
      },
      actions: error.recoverable
        ? [
            {
              id: 'retry',
              label: 'Retry',
              command: command.raw_input,
              type: 'primary' as const,
            },
          ]
        : undefined,
      undo_available: false,
    };
  }

  /**
   * Handle draft created result
   */
  handleDraftCreated(command: Command, draftId: string): FormattedResult {
    return {
      success: true,
      message: 'Your request requires approval before execution. A draft has been created.',
      data: { draft_id: draftId },
      actions: [
        {
          id: 'view_draft',
          label: 'View Draft',
          command: `view draft ${draftId}`,
          type: 'primary' as const,
        },
        {
          id: 'cancel_draft',
          label: 'Cancel Request',
          command: `cancel draft ${draftId}`,
          type: 'secondary' as const,
        },
      ],
      undo_available: false,
      next_suggestions: [
        'Check pending approvals',
        'View my drafts',
      ],
    };
  }

  /**
   * Handle waiting for approval
   */
  handleAwaitingApproval(command: Command, approvalId: string): FormattedResult {
    return {
      success: true,
      message: 'Approval request submitted. You will be notified once it is reviewed.',
      data: { approval_id: approvalId },
      actions: [
        {
          id: 'check_status',
          label: 'Check Status',
          command: `check approval ${approvalId}`,
          type: 'primary' as const,
        },
      ],
      undo_available: false,
    };
  }

  /**
   * Get result history for session
   */
  getHistory(sessionId: string): CommandResult[] {
    return this.resultHistory.get(sessionId) || [];
  }

  /**
   * Clear history for session
   */
  clearHistory(sessionId: string): void {
    this.resultHistory.delete(sessionId);
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Generate success message based on command
   */
  private generateSuccessMessage(command: Command): string {
    const messages: Record<string, string> = {
      create_ticket: 'Ticket created successfully',
      update_ticket: 'Ticket updated successfully',
      close_ticket: 'Ticket closed successfully',
      assign_ticket: 'Ticket assigned successfully',
      escalate_ticket: 'Ticket escalated successfully',
      merge_tickets: 'Tickets merged successfully',
      search_tickets: 'Search completed',
      view_ticket: 'Ticket details loaded',
      prioritize_ticket: 'Priority updated successfully',
      tag_ticket: 'Tag updated successfully',
      view_customer: 'Customer profile loaded',
      search_customer: 'Search completed',
      view_customer_history: 'Customer history loaded',
      view_agent_status: 'Agent status loaded',
      view_workload: 'Workload data loaded',
      generate_report: 'Report generated successfully',
      view_statistics: 'Statistics loaded',
      export_data: 'Export completed',
      check_health: 'System health check completed',
      view_alerts: 'Alerts loaded',
      acknowledge_alert: 'Alert acknowledged',
      search_knowledge: 'Knowledge base search completed',
      suggest_response: 'Response suggestions loaded',
      send_message: 'Message sent successfully',
      schedule_followup: 'Follow-up scheduled successfully',
      create_note: 'Note added successfully',
      get_help: 'Help information loaded',
      list_commands: 'Commands list loaded',
    };

    return messages[command.intent.intent] || 'Command executed successfully';
  }

  /**
   * Generate follow-up actions
   */
  private generateActions(command: Command, result: CommandResult): ResultAction[] {
    const actions: ResultAction[] = [];

    // Add undo action if available
    if (result.undo_available) {
      actions.push({
        id: 'undo',
        label: 'Undo',
        command: result.undo_command || `undo ${command.id}`,
        type: 'secondary' as const,
      });
    }

    // Add context-specific actions
    switch (command.intent.intent) {
      case 'create_ticket':
        actions.push({
          id: 'view_ticket',
          label: 'View Ticket',
          command: `view ticket ${(result.data as { ticket_id?: string })?.ticket_id}`,
          type: 'primary' as const,
        });
        break;

      case 'search_tickets':
        actions.push({
          id: 'create_ticket',
          label: 'Create Ticket',
          command: 'create ticket',
          type: 'primary' as const,
        });
        break;

      case 'view_ticket':
        actions.push(
          {
            id: 'add_note',
            label: 'Add Note',
            command: 'add note',
            type: 'primary' as const,
          },
          {
            id: 'close_ticket',
            label: 'Close Ticket',
            command: `close ticket`,
            type: 'secondary' as const,
          }
        );
        break;
    }

    return actions;
  }

  /**
   * Generate next action suggestions
   */
  private generateSuggestions(command: Command): string[] {
    const suggestions: Record<string, string[]> = {
      create_ticket: ['Assign ticket to agent', 'Add tags'],
      close_ticket: ['View closed tickets', 'Create follow-up'],
      search_tickets: ['Filter by priority', 'View ticket details'],
      view_customer: ['View customer history', 'Create ticket for customer'],
      generate_report: ['Export report', 'Schedule report'],
      view_statistics: ['Generate detailed report', 'View trends'],
    };

    return suggestions[command.intent.intent] || [];
  }

  /**
   * Add result to history
   */
  private addToHistory(sessionId: string, result: CommandResult): void {
    if (!this.resultHistory.has(sessionId)) {
      this.resultHistory.set(sessionId, []);
    }

    const history = this.resultHistory.get(sessionId)!;
    history.push(result);

    // Keep last 50 results
    if (history.length > 50) {
      history.shift();
    }
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createResultHandler(): ResultHandler {
  return new ResultHandler();
}
