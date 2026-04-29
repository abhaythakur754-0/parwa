/**
 * JARVIS Command Processing Types (Week 3 - Phase 1)
 *
 * Type definitions for the Command Processing system.
 * Covers: Intent classification, Entity extraction, Context management,
 * Command routing, Execution engine, Draft creation, Approval workflow
 */

// ── Intent Types ─────────────────────────────────────────────────────

export type IntentCategory =
  | 'ticket' // Ticket operations
  | 'customer' // Customer operations
  | 'agent' // Agent operations
  | 'analytics' // Analytics and reporting
  | 'system' // System operations
  | 'knowledge' // Knowledge base operations
  | 'communication' // Communication operations
  | 'automation' // Automation operations
  | 'help' // Help and information
  | 'unknown'; // Unknown intent

export type IntentAction =
  // Ticket intents
  | 'create_ticket'
  | 'update_ticket'
  | 'close_ticket'
  | 'assign_ticket'
  | 'escalate_ticket'
  | 'merge_tickets'
  | 'search_tickets'
  | 'view_ticket'
  | 'prioritize_ticket'
  | 'tag_ticket'
  // Customer intents
  | 'view_customer'
  | 'search_customer'
  | 'update_customer'
  | 'merge_customers'
  | 'view_customer_history'
  // Agent intents
  | 'view_agent_status'
  | 'assign_to_agent'
  | 'view_workload'
  | 'reassign_tickets'
  // Analytics intents
  | 'generate_report'
  | 'view_statistics'
  | 'view_trends'
  | 'export_data'
  // System intents
  | 'check_health'
  | 'view_alerts'
  | 'acknowledge_alert'
  | 'configure_settings'
  | 'check_sla_status'
  // Knowledge intents
  | 'search_knowledge'
  | 'create_article'
  | 'update_article'
  | 'suggest_response'
  // Communication intents
  | 'send_message'
  | 'schedule_followup'
  | 'create_note'
  | 'set_reminder'
  // Refund intents
  | 'refund_request'
  | 'return_request'
  // Account intents
  | 'email_change'
  | 'password_change'
  | 'billing_change'
  // Special action intents
  | 'vip_action'
  | 'policy_exception'
  | 'financial_transaction'
  // Automation intents
  | 'create_rule'
  | 'update_rule'
  | 'view_automations'
  // Help intents
  | 'get_help'
  | 'list_commands'
  | 'explain_feature'
  // Daily intents
  | 'daily_briefing'
  | 'daily_summary';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

// ── Entity Types ─────────────────────────────────────────────────────

export type EntityType =
  | 'ticket_id'
  | 'customer_id'
  | 'agent_id'
  | 'team_id'
  | 'priority'
  | 'status'
  | 'category'
  | 'tag'
  | 'date'
  | 'time'
  | 'duration'
  | 'number'
  | 'email'
  | 'phone'
  | 'url'
  | 'keyword'
  | 'channel'
  | 'metric'
  | 'filter'
  | 'sort_order'
  | 'limit';

// ── Intent Result ────────────────────────────────────────────────────

export interface IntentResult {
  intent: IntentAction;
  category: IntentCategory;
  confidence: number; // 0-1
  confidence_level: ConfidenceLevel;
  alternative_intents?: Array<{
    intent: IntentAction;
    confidence: number;
  }>;
  raw_text: string;
  normalized_text: string;
}

// ── Entity Result ────────────────────────────────────────────────────

export interface EntityResult {
  type: EntityType;
  value: string;
  normalized_value?: string | number | Date;
  start_index: number;
  end_index: number;
  confidence: number;
  source: 'extracted' | 'inferred' | 'default';
}

export interface ExtractionResult {
  entities: EntityResult[];
  raw_text: string;
  extraction_time_ms: number;
}

// ── Command Types ────────────────────────────────────────────────────

export type ExecutionMode = 'direct' | 'draft';

export type CommandStatus =
  | 'pending'
  | 'validated'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'awaiting_approval';

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired';

export interface Command {
  id: string;
  session_id: string;
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  raw_input: string;
  intent: IntentResult;
  entities: EntityResult[];
  action: CommandAction;
  mode: ExecutionMode;
  status: CommandStatus;
  created_at: Date;
  executed_at?: Date;
  completed_at?: Date;
  result?: CommandResult;
  error?: CommandError;
  metadata: Record<string, unknown>;
}

export interface CommandAction {
  type: IntentAction;
  category: IntentCategory;
  handler: string;
  params: Record<string, unknown>;
  required_params: string[];
  optional_params: string[];
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  reversible: boolean;
  timeout_ms: number;
}

export interface CommandResult {
  success: boolean;
  data?: unknown;
  message?: string;
  affected_records?: number;
  side_effects?: string[];
  undo_available: boolean;
  undo_command?: string;
}

export interface CommandError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  recoverable: boolean;
  suggested_fix?: string;
}

// ── Draft Types ──────────────────────────────────────────────────────

export interface Draft {
  id: string;
  command_id: string;
  tenant_id: string;
  session_id: string;
  action: CommandAction;
  preview: DraftPreview;
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'expired';
  created_at: Date;
  expires_at: Date;
  approved_by?: string;
  approved_at?: Date;
  rejection_reason?: string;
  execution_result?: CommandResult;
}

export interface DraftPreview {
  title: string;
  description: string;
  changes: DraftChange[];
  affected_items: AffectedItem[];
  warnings: string[];
  estimated_impact: 'low' | 'medium' | 'high';
}

export interface DraftChange {
  field: string;
  current_value: unknown;
  new_value: unknown;
  description: string;
}

export interface AffectedItem {
  type: 'ticket' | 'customer' | 'agent' | 'automation';
  id: string;
  name?: string;
}

// ── Approval Types ───────────────────────────────────────────────────

export interface ApprovalRequest {
  id: string;
  draft_id: string;
  command_id: string;
  tenant_id: string;
  requested_by: string;
  approver_roles: string[];
  approver_ids?: string[];
  status: ApprovalStatus;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  reason: string;
  created_at: Date;
  expires_at: Date;
  approvals: ApprovalRecord[];
  rejections: ApprovalRecord[];
  min_approvals: number;
  current_approvals: number;
  metadata: Record<string, unknown>;
}

export interface ApprovalRecord {
  approver_id: string;
  approver_name: string;
  action: 'approved' | 'rejected';
  timestamp: Date;
  comment?: string;
}

// ── Context Types ────────────────────────────────────────────────────

export interface CommandContext {
  session_id: string;
  tenant_id: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  user_id: string;
  user_role: string;
  conversation_history: ConversationTurn[];
  current_ticket?: string;
  current_customer?: string;
  current_agent?: string;
  active_filters: Record<string, unknown>;
  page_context?: string;
  timezone: string;
  locale: string;
  preferences: UserPreferences;
  permissions: string[];
  created_at: Date;
  updated_at: Date;
}

export interface ConversationTurn {
  id: string;
  role: 'user' | 'jarvis' | 'system';
  content: string;
  intent?: IntentAction;
  entities?: EntityResult[];
  timestamp: Date;
  command_id?: string;
}

export interface UserPreferences {
  default_channel?: string;
  default_priority?: string;
  confirmation_required: boolean;
  notification_preferences: Record<string, boolean>;
  display_format: 'compact' | 'detailed';
}

// ── Routing Types ────────────────────────────────────────────────────

export interface RouteDefinition {
  intent: IntentAction;
  handler: string;
  validator?: string;
  params_schema: ParamSchema;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  execution_mode: ExecutionMode;
  required_permissions: string[];
  variant_availability: ('mini_parwa' | 'parwa' | 'parwa_high')[];
  rate_limit?: {
    max_requests: number;
    window_ms: number;
  };
}

export interface ParamSchema {
  required: ParamDefinition[];
  optional: ParamDefinition[];
}

export interface ParamDefinition {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'date' | 'array' | 'object';
  description: string;
  validation?: ValidationRule[];
  default?: unknown;
  enum?: string[];
}

export interface ValidationRule {
  type: 'min' | 'max' | 'pattern' | 'enum' | 'custom';
  value: unknown;
  message: string;
}

// ── Execution Types ──────────────────────────────────────────────────

export interface ExecutionContext {
  command: Command;
  context: CommandContext;
  transaction_id: string;
  started_at: Date;
  checkpoints: ExecutionCheckpoint[];
}

export interface ExecutionCheckpoint {
  id: string;
  step: string;
  status: 'pending' | 'completed' | 'failed' | 'rolled_back';
  timestamp: Date;
  data?: Record<string, unknown>;
  rollback_data?: Record<string, unknown>;
}

export type ExecutionResult = CommandResult;

// ── Handler Types ────────────────────────────────────────────────────

export type CommandHandler = (
  params: Record<string, unknown>,
  context: ExecutionContext
) => Promise<CommandResult>;

export type CommandValidator = (
  params: Record<string, unknown>,
  context: CommandContext
) => Promise<{ valid: boolean; errors?: string[] }>;

// ── API Request/Response Types ───────────────────────────────────────

export interface ProcessCommandRequest {
  text: string;
  session_id: string;
  context?: Partial<CommandContext>;
}

export interface ProcessCommandResponse {
  command: Command;
  draft?: Draft;
  approval_required: boolean;
  message: string;
  suggestions?: string[];
}

export interface ApproveDraftRequest {
  draft_id: string;
  approved_by: string;
  comment?: string;
}

export interface RejectDraftRequest {
  draft_id: string;
  rejected_by: string;
  reason: string;
}

export interface GetPendingApprovalsRequest {
  tenant_id: string;
  user_id?: string;
  role?: string;
  limit?: number;
}

export interface GetPendingApprovalsResponse {
  approvals: ApprovalRequest[];
  total: number;
}

// ── Variant-specific Command Limits ───────────────────────────────────

export const VARIANT_COMMAND_LIMITS: Record<
  string,
  {
    max_commands_per_day: number;
    max_drafts_per_day: number;
    draft_expiry_hours: number;
    approval_timeout_hours: number;
    allowed_risk_levels: ('low' | 'medium' | 'high' | 'critical')[];
  }
> = {
  mini_parwa: {
    max_commands_per_day: 100,
    max_drafts_per_day: 5,
    draft_expiry_hours: 1,
    approval_timeout_hours: 4,
    allowed_risk_levels: ['low'],
  },
  parwa: {
    max_commands_per_day: 500,
    max_drafts_per_day: 20,
    draft_expiry_hours: 4,
    approval_timeout_hours: 24,
    allowed_risk_levels: ['low', 'medium'],
  },
  parwa_high: {
    max_commands_per_day: 2000,
    max_drafts_per_day: 100,
    draft_expiry_hours: 24,
    approval_timeout_hours: 48,
    allowed_risk_levels: ['low', 'medium', 'high'],
  },
};

// ── Risk Level Definitions ───────────────────────────────────────────

export const RISK_LEVEL_DEFINITIONS: Record<
  'low' | 'medium' | 'high' | 'critical',
  {
    description: string;
    requires_approval: boolean;
    reversible: boolean;
    notification_channels: string[];
  }
> = {
  low: {
    description: 'Safe operations with minimal impact',
    requires_approval: false,
    reversible: true,
    notification_channels: [],
  },
  medium: {
    description: 'Operations that affect multiple records or settings',
    requires_approval: false,
    reversible: true,
    notification_channels: ['dashboard'],
  },
  high: {
    description: 'Operations that could significantly impact customers or data',
    requires_approval: true,
    reversible: true,
    notification_channels: ['dashboard', 'email'],
  },
  critical: {
    description: 'Operations with irreversible effects or major business impact',
    requires_approval: true,
    reversible: false,
    notification_channels: ['dashboard', 'email', 'slack'],
  },
};
