/**
 * JARVIS Command Processing - Week 3 (Phase 1)
 *
 * Complete implementation of the JARVIS Command Processing system.
 * Handles natural language command processing, execution, and approvals.
 *
 * Components:
 * - Intent Classifier: Classifies user intents from natural language
 * - Entity Extractor: Extracts entities (IDs, dates, priorities) from text
 * - Context Manager: Manages conversation context and state
 * - Command Router: Routes intents to handlers with validation
 * - Safe Action Executor: Executes low-risk commands directly
 * - Draft Creator: Creates drafts for high-risk operations
 * - Approval Workflow: Manages approval process for drafts
 * - Result Handler: Formats and handles execution results
 */

// Main Processor
export {
  CommandProcessor,
  createCommandProcessor,
  getCommandProcessor,
  shutdownCommandProcessor,
} from './command-processor';
export type { CommandProcessorConfig } from './command-processor';

// Components
export { IntentClassifier, createIntentClassifier, INTENT_PATTERNS } from './intent-classifier';
export { EntityExtractor, createEntityExtractor, ENTITY_PATTERNS, INTENT_ENTITY_EXPECTATIONS } from './entity-extractor';
export { ContextManager, createContextManager, getContextManager } from './context-manager';
export { CommandRouter, createCommandRouter, ROUTE_DEFINITIONS } from './command-router';
export { SafeActionExecutor, createSafeActionExecutor } from './safe-executor';
export { DraftCreator, createDraftCreator } from './draft-creator';
export { ApprovalWorkflow, createApprovalWorkflow } from './approval-workflow';
export { ResultHandler, createResultHandler } from './result-handler';
export type { FormattedResult, ResultAction } from './result-handler';

// Re-export types
export type {
  IntentCategory,
  IntentAction,
  ConfidenceLevel,
  IntentResult,
  EntityType,
  EntityResult,
  ExtractionResult,
  ExecutionMode,
  CommandStatus,
  ApprovalStatus,
  Command,
  CommandAction,
  CommandResult,
  CommandError,
  Draft,
  DraftPreview,
  DraftChange,
  AffectedItem,
  ApprovalRequest,
  ApprovalRecord,
  CommandContext,
  ConversationTurn,
  UserPreferences,
  RouteDefinition,
  ParamSchema,
  ParamDefinition,
  ValidationRule,
  ExecutionContext,
  ExecutionCheckpoint,
  CommandHandler,
  CommandValidator,
  ProcessCommandRequest,
  ProcessCommandResponse,
  ApproveDraftRequest,
  RejectDraftRequest,
  GetPendingApprovalsRequest,
  GetPendingApprovalsResponse,
  VARIANT_COMMAND_LIMITS,
  RISK_LEVEL_DEFINITIONS,
} from '@/types/command';
