/**
 * JARVIS Safe Action Executor (Week 3 - Phase 1)
 *
 * Executes safe (low-risk) commands directly without approval.
 * Handles execution, rollback, and result handling for direct execution mode.
 */

import type {
  Command,
  CommandAction,
  CommandContext,
  CommandResult,
  CommandError,
  ExecutionContext,
  ExecutionCheckpoint,
  CommandHandler,
} from '@/types/command';

// ── Handler Registry ──────────────────────────────────────────────────

type HandlerRegistry = Map<string, CommandHandler>;

// ── Safe Action Executor Class ────────────────────────────────────────

export class SafeActionExecutor {
  private handlers: HandlerRegistry = new Map();
  private activeExecutions: Map<string, ExecutionContext> = new Map();

  constructor() {
    this.registerDefaultHandlers();
  }

  /**
   * Register a command handler
   */
  registerHandler(handlerName: string, handler: CommandHandler): void {
    this.handlers.set(handlerName, handler);
  }

  /**
   * Execute a command directly
   */
  async execute(command: Command, context: CommandContext): Promise<CommandResult> {
    const executionContext = this.createExecutionContext(command, context);
    this.activeExecutions.set(command.id, executionContext);

    try {
      // Pre-execution checkpoint
      this.addCheckpoint(executionContext, 'start', 'pending');

      // Get handler
      const handler = this.handlers.get(command.action.handler);
      if (!handler) {
        return this.handleError(executionContext, {
          code: 'HANDLER_NOT_FOUND',
          message: `No handler registered for: ${command.action.handler}`,
          recoverable: false,
        });
      }

      // Execute
      this.addCheckpoint(executionContext, 'execute', 'pending');
      const result = await this.executeWithTimeout(
        handler,
        command.action.params,
        executionContext,
        command.action.timeout_ms
      );

      // Success checkpoint
      this.addCheckpoint(executionContext, 'complete', 'completed', { result });

      return result;
    } catch (error) {
      return this.handleError(executionContext, {
        code: 'EXECUTION_ERROR',
        message: (error as Error).message,
        recoverable: true,
      });
    } finally {
      this.activeExecutions.delete(command.id);
    }
  }

  /**
   * Check if action is safe for direct execution
   */
  isSafeForDirectExecution(action: CommandAction, context: CommandContext): boolean {
    // Check risk level
    const allowedRiskLevels = {
      mini_parwa: ['low'],
      parwa: ['low', 'medium'],
      parwa_high: ['low', 'medium', 'high'],
    };

    const allowed = allowedRiskLevels[context.variant] || ['low'];
    if (!allowed.includes(action.risk_level)) {
      return false;
    }

    // Check if reversible
    if (!action.reversible && action.risk_level !== 'low') {
      return false;
    }

    // Check permissions
    const requiredPermissions = this.getRequiredPermissions(action.handler);
    for (const perm of requiredPermissions) {
      if (!context.permissions.includes(perm)) {
        return false;
      }
    }

    return true;
  }

  /**
   * Get active executions
   */
  getActiveExecutions(): ExecutionContext[] {
    return Array.from(this.activeExecutions.values());
  }

  /**
   * Cancel execution
   */
  async cancelExecution(commandId: string): Promise<boolean> {
    const execution = this.activeExecutions.get(commandId);
    if (!execution) return false;

    // Mark as cancelled
    this.addCheckpoint(execution, 'cancelled', 'failed');

    // Attempt rollback if possible
    await this.rollback(execution);

    this.activeExecutions.delete(commandId);
    return true;
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Create execution context
   */
  private createExecutionContext(command: Command, context: CommandContext): ExecutionContext {
    return {
      command,
      context,
      transaction_id: `txn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      started_at: new Date(),
      checkpoints: [],
    };
  }

  /**
   * Add checkpoint to execution
   */
  private addCheckpoint(
    execution: ExecutionContext,
    step: string,
    status: ExecutionCheckpoint['status'],
    data?: Record<string, unknown>
  ): void {
    execution.checkpoints.push({
      id: `cp_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      step,
      status,
      timestamp: new Date(),
      data,
    });
  }

  /**
   * Execute with timeout
   */
  private async executeWithTimeout(
    handler: CommandHandler,
    params: Record<string, unknown>,
    context: ExecutionContext,
    timeoutMs: number
  ): Promise<CommandResult> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error(`Execution timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      handler(params, context)
        .then((result) => {
          clearTimeout(timeout);
          resolve(result);
        })
        .catch((error) => {
          clearTimeout(timeout);
          reject(error);
        });
    });
  }

  /**
   * Handle execution error
   */
  private handleError(execution: ExecutionContext, error: CommandError): CommandResult {
    this.addCheckpoint(execution, 'error', 'failed', { error });

    return {
      success: false,
      message: error.message,
      undo_available: execution.command.action.reversible,
    };
  }

  /**
   * Rollback execution
   */
  private async rollback(execution: ExecutionContext): Promise<void> {
    // Find checkpoints with rollback data
    const rollbackPoints = execution.checkpoints.filter(
      (cp) => cp.rollback_data && cp.status === 'completed'
    );

    // Rollback in reverse order
    for (const point of rollbackPoints.reverse()) {
      try {
        // Execute rollback logic based on checkpoint data
        console.log(`Rolling back checkpoint: ${point.step}`);
      } catch (error) {
        console.error(`Rollback failed for checkpoint ${point.step}:`, error);
      }
    }
  }

  /**
   * Get required permissions for handler
   */
  private getRequiredPermissions(handlerName: string): string[] {
    const permissionMap: Record<string, string[]> = {
      'ticket_handler.create': ['ticket.create'],
      'ticket_handler.update': ['ticket.update'],
      'ticket_handler.close': ['ticket.close'],
      'ticket_handler.assign': ['ticket.assign'],
      'ticket_handler.escalate': ['ticket.escalate'],
      'customer_handler.view': ['customer.view'],
      'analytics_handler.export': ['analytics.export'],
    };
    return permissionMap[handlerName] || [];
  }

  /**
   * Register default mock handlers
   */
  private registerDefaultHandlers(): void {
    // Ticket handlers
    this.registerHandler('ticket_handler.view', async (params) => ({
      success: true,
      data: { ticket_id: params.ticket_id, status: 'mock_data' },
      undo_available: false,
    }));

    this.registerHandler('ticket_handler.create', async (params) => ({
      success: true,
      data: { ticket_id: `TKT-${Date.now()}`, ...params },
      message: 'Ticket created successfully',
      undo_available: true,
    }));

    this.registerHandler('ticket_handler.update', async (params) => ({
      success: true,
      data: params,
      message: 'Ticket updated successfully',
      undo_available: true,
    }));

    this.registerHandler('ticket_handler.close', async (params) => ({
      success: true,
      data: params,
      message: 'Ticket closed successfully',
      undo_available: true,
    }));

    this.registerHandler('ticket_handler.assign', async (params) => ({
      success: true,
      data: params,
      message: 'Ticket assigned successfully',
      undo_available: true,
    }));

    this.registerHandler('ticket_handler.search', async (params) => ({
      success: true,
      data: [],
      message: 'Ticket search completed',
      undo_available: false,
    }));

    this.registerHandler('ticket_handler.prioritize', async (params) => ({
      success: true,
      data: params,
      message: 'Ticket priority updated',
      undo_available: true,
    }));

    this.registerHandler('ticket_handler.tag', async (params) => ({
      success: true,
      data: params,
      message: 'Ticket tagged successfully',
      undo_available: true,
    }));

    // Agent handlers
    this.registerHandler('agent_handler.status', async (params) => ({
      success: true,
      data: { agents: [], status: 'available' },
      message: 'Agent status retrieved',
      undo_available: false,
    }));

    this.registerHandler('agent_handler.workload', async (params) => ({
      success: true,
      data: { workload: {} },
      message: 'Workload retrieved',
      undo_available: false,
    }));

    // Customer handlers
    this.registerHandler('customer_handler.view', async (params) => ({
      success: true,
      data: { customer_id: params.customer_id, name: 'Mock Customer' },
      undo_available: false,
    }));

    this.registerHandler('customer_handler.search', async (params) => ({
      success: true,
      data: [],
      message: 'Search completed',
      undo_available: false,
    }));

    // Analytics handlers
    this.registerHandler('analytics_handler.statistics', async (params) => ({
      success: true,
      data: { metrics: {} },
      undo_available: false,
    }));

    // System handlers
    this.registerHandler('system_handler.health', async () => ({
      success: true,
      data: { status: 'healthy', components: [] },
      undo_available: false,
    }));

    this.registerHandler('system_handler.alerts', async () => ({
      success: true,
      data: { alerts: [] },
      undo_available: false,
    }));

    // Help handlers
    this.registerHandler('help_handler.get_help', async (params) => ({
      success: true,
      data: { topic: params.topic, help_text: 'Help content' },
      undo_available: false,
    }));

    this.registerHandler('help_handler.list_commands', async () => ({
      success: true,
      data: { commands: [] },
      message: 'Available commands listed',
      undo_available: false,
    }));
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createSafeActionExecutor(): SafeActionExecutor {
  return new SafeActionExecutor();
}
