/**
 * JARVIS Command Processor (Week 3 - Phase 1)
 *
 * Main orchestrator for command processing.
 * Integrates: Intent classifier, Entity extractor, Context manager,
 * Command router, Safe executor, Draft creator, Approval workflow.
 */

import type {
  Command,
  CommandContext,
  CommandAction,
  CommandResult,
  IntentResult,
  EntityResult,
  Draft,
  ApprovalRequest,
  ProcessCommandRequest,
  ProcessCommandResponse,
  ExecutionMode,
} from '@/types/command';

import { IntentClassifier, createIntentClassifier } from './intent-classifier';
import { EntityExtractor, createEntityExtractor } from './entity-extractor';
import { ContextManager, getContextManager } from './context-manager';
import { CommandRouter, createCommandRouter } from './command-router';
import { SafeActionExecutor, createSafeActionExecutor } from './safe-executor';
import { DraftCreator, createDraftCreator } from './draft-creator';
import { ApprovalWorkflow, createApprovalWorkflow } from './approval-workflow';
import { ResultHandler, createResultHandler, FormattedResult } from './result-handler';

// ── Command Processor Configuration ───────────────────────────────────

export interface CommandProcessorConfig {
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
}

// ── Command Processor Class ───────────────────────────────────────────

export class CommandProcessor {
  private config: CommandProcessorConfig;
  private initialized = false;

  // Components
  private intentClassifier!: IntentClassifier;
  private entityExtractor!: EntityExtractor;
  private contextManager!: ContextManager;
  private commandRouter!: CommandRouter;
  private safeExecutor!: SafeActionExecutor;
  private draftCreator!: DraftCreator;
  private approvalWorkflow!: ApprovalWorkflow;
  private resultHandler!: ResultHandler;

  // State
  private commandHistory: Map<string, Command[]> = new Map();

  constructor(config: CommandProcessorConfig) {
    this.config = config;
  }

  /**
   * Initialize the command processor
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    this.intentClassifier = createIntentClassifier();
    this.entityExtractor = createEntityExtractor();
    this.contextManager = getContextManager();
    this.commandRouter = createCommandRouter();
    this.safeExecutor = createSafeActionExecutor();
    this.draftCreator = createDraftCreator();
    this.approvalWorkflow = createApprovalWorkflow();
    this.resultHandler = createResultHandler();

    this.initialized = true;
  }

  /**
   * Process a command from natural language
   */
  async process(request: ProcessCommandRequest): Promise<ProcessCommandResponse> {
    await this.ensureInitialized();

    const { text, session_id, context: initialContext } = request;

    // Get or create context
    const context = this.contextManager.getContext(session_id, {
      tenant_id: this.config.tenant_id,
      variant: this.config.variant,
      ...initialContext,
    });

    // 1. Classify intent
    const intent = this.intentClassifier.classify(text, context);

    // 2. Extract entities
    const extraction = this.entityExtractor.extract(text, intent.intent);
    const entities = extraction.entities;

    // 3. Route to action
    const params = this.entityExtractor.entitiesToParams(entities);
    const action = this.commandRouter.route(intent.intent, params, context);

    // 4. Create command object
    const command = this.createCommand(session_id, text, intent, entities, action);

    // 5. Add turn to context
    this.contextManager.addTurn(session_id, {
      role: 'user',
      content: text,
      intent: intent.intent,
      entities,
      command_id: command.id,
    });

    // 6. Determine execution path
    const mode = this.determineExecutionMode(action, context);

    // 7. Execute or create draft
    let result: FormattedResult;
    let draft: Draft | undefined;
    let approvalRequired = false;

    if (mode === 'direct') {
      // Direct execution
      const executionResult = await this.safeExecutor.execute(command, context);
      result = this.resultHandler.handleSuccess(command, executionResult);
      command.status = executionResult.success ? 'completed' : 'failed';
      command.result = executionResult;
    } else {
      // Create draft for approval
      draft = await this.draftCreator.createDraft(command);
      command.status = 'awaiting_approval';
      result = this.resultHandler.handleDraftCreated(command, draft.id);
      approvalRequired = true;
    }

    // 8. Add Jarvis response to context
    this.contextManager.addTurn(session_id, {
      role: 'jarvis',
      content: result.message,
      command_id: command.id,
    });

    // 9. Store in history
    this.addToHistory(session_id, command);

    return {
      command,
      draft,
      approval_required: approvalRequired,
      message: result.message,
      suggestions: result.next_suggestions,
    };
  }

  /**
   * Approve a draft
   */
  async approveDraft(
    draftId: string,
    approvedBy: string,
    comment?: string
  ): Promise<FormattedResult> {
    await this.ensureInitialized();

    const draft = this.draftCreator.getDraft(draftId);
    if (!draft) {
      return {
        success: false,
        message: 'Draft not found',
        undo_available: false,
      };
    }

    // Approve the draft
    const updatedDraft = await this.draftCreator.approveDraft(draftId, approvedBy);
    if (!updatedDraft) {
      return {
        success: false,
        message: 'Failed to approve draft',
        undo_available: false,
      };
    }

    // Get context
    const context = this.contextManager.getContext(draft.session_id);

    // Execute the command
    const command = this.createCommandFromDraft(draft);
    const result = await this.safeExecutor.execute(command, context);

    // Update draft
    this.draftCreator.markExecuted(draftId, result);

    return this.resultHandler.handleSuccess(command, result);
  }

  /**
   * Reject a draft
   */
  rejectDraft(draftId: string, rejectedBy: string, reason: string): FormattedResult {
    const updatedDraft = this.draftCreator.rejectDraft(draftId, rejectedBy, reason);

    if (!updatedDraft) {
      return {
        success: false,
        message: 'Draft not found or already processed',
        undo_available: false,
      };
    }

    return {
      success: true,
      message: 'Draft rejected successfully',
      undo_available: false,
    };
  }

  /**
   * Get pending approvals for user
   */
  getPendingApprovals(
    userId: string,
    userRole: string
  ): ApprovalRequest[] {
    return this.approvalWorkflow.getPendingApprovalsForUser(
      userId,
      userRole,
      this.config.tenant_id
    );
  }

  /**
   * Get command suggestions
   */
  getSuggestions(text: string, sessionId: string): Array<{
    intent: string;
    description: string;
    confidence: number;
  }> {
    const context = this.contextManager.getContext(sessionId);
    return this.intentClassifier.suggest(text, context);
  }

  /**
   * Get available commands for variant
   */
  getAvailableCommands(): string[] {
    return this.commandRouter.getAvailableIntents(this.config.variant);
  }

  /**
   * Get context summary
   */
  getContextSummary(sessionId: string): string {
    return this.contextManager.getContextSummary(sessionId);
  }

  /**
   * Clear session
   */
  clearSession(sessionId: string): void {
    this.contextManager.clearContext(sessionId);
    this.commandHistory.delete(sessionId);
    this.intentClassifier.clearHistory(sessionId);
    this.resultHandler.clearHistory(sessionId);
  }

  /**
   * Shutdown processor
   */
  async shutdown(): Promise<void> {
    this.contextManager.shutdown();
    this.draftCreator.shutdown();
    this.approvalWorkflow.shutdown();
    this.commandHistory.clear();
    this.initialized = false;
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Ensure processor is initialized
   */
  private async ensureInitialized(): Promise<void> {
    if (!this.initialized) {
      await this.initialize();
    }
  }

  /**
   * Create command object
   */
  private createCommand(
    sessionId: string,
    rawInput: string,
    intent: IntentResult,
    entities: EntityResult[],
    action: CommandAction
  ): Command {
    return {
      id: this.generateCommandId(),
      session_id: sessionId,
      tenant_id: this.config.tenant_id,
      variant: this.config.variant,
      raw_input: rawInput,
      intent,
      entities,
      action,
      mode: this.determineExecutionMode(action, this.contextManager.getContext(sessionId)),
      status: 'pending',
      created_at: new Date(),
      metadata: {},
    };
  }

  /**
   * Create command from draft
   */
  private createCommandFromDraft(draft: Draft): Command {
    return {
      id: this.generateCommandId(),
      session_id: draft.session_id,
      tenant_id: draft.tenant_id,
      variant: this.config.variant,
      raw_input: '',
      intent: {
        intent: draft.action.type,
        category: draft.action.category,
        confidence: 1,
        confidence_level: 'high',
        raw_text: '',
        normalized_text: '',
      },
      entities: [],
      action: draft.action,
      mode: 'direct',
      status: 'pending',
      created_at: new Date(),
      metadata: { draft_id: draft.id },
    };
  }

  /**
   * Determine execution mode
   */
  private determineExecutionMode(action: CommandAction, context: CommandContext): ExecutionMode {
    // Check if safe for direct execution
    if (this.safeExecutor.isSafeForDirectExecution(action, context)) {
      return 'direct';
    }
    return 'draft';
  }

  /**
   * Add command to history
   */
  private addToHistory(sessionId: string, command: Command): void {
    if (!this.commandHistory.has(sessionId)) {
      this.commandHistory.set(sessionId, []);
    }

    const history = this.commandHistory.get(sessionId)!;
    history.push(command);

    // Keep last 100 commands
    if (history.length > 100) {
      history.shift();
    }
  }

  /**
   * Generate command ID
   */
  private generateCommandId(): string {
    return `cmd_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// ── Singleton Registry ────────────────────────────────────────────────

const processors = new Map<string, CommandProcessor>();

export async function getCommandProcessor(
  config: CommandProcessorConfig
): Promise<CommandProcessor> {
  const key = `${config.tenant_id}_${config.variant}`;

  if (!processors.has(key)) {
    const processor = new CommandProcessor(config);
    await processor.initialize();
    processors.set(key, processor);
  }

  return processors.get(key)!;
}

export async function shutdownCommandProcessor(config: CommandProcessorConfig): Promise<void> {
  const key = `${config.tenant_id}_${config.variant}`;
  const processor = processors.get(key);

  if (processor) {
    await processor.shutdown();
    processors.delete(key);
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createCommandProcessor(config: CommandProcessorConfig): CommandProcessor {
  return new CommandProcessor(config);
}
