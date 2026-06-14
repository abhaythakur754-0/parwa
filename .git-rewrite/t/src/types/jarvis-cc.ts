/**
 * PARWA Jarvis Customer Care Types (Phase 5 — Jarvis CC Dashboard)
 *
 * TypeScript type definitions for the Jarvis Customer Care system.
 * Mirrors backend Pydantic schemas from backend/app/schemas/jarvis_cc.py
 */

// ── Core Enums ──────────────────────────────────────────────────────

export type CCMessageType =
  | 'text'
  | 'variant_pipeline'
  | 'ai_generated'
  | 'direct_ai'
  | 'error'
  | 'proactive_alert'
  | 'command_response';

export type CCChannel = 'chat' | 'email' | 'sms' | 'voice' | 'whatsapp' | 'social';

export type TickType = 'periodic' | 'on_change' | 'manual' | 'emergency';

export type AlertSeverity = 'info' | 'warning' | 'critical' | 'emergency';

export type AlertStatus = 'active' | 'acknowledged' | 'dismissed' | 'resolved' | 'expired';

export type AlertCategory =
  | 'system_health'
  | 'ticket_volume'
  | 'agent_pool'
  | 'quality'
  | 'drift'
  | 'billing'
  | 'security'
  | 'integration'
  | 'training';

export type CommandIntent = 'query' | 'control' | 'configure' | 'report' | 'override';

export type CommandSource = 'chat' | 'api' | 'co_pilot' | 'proactive' | 'scheduled';

export type CommandStatus = 'received' | 'parsing' | 'parsed' | 'executing' | 'completed' | 'failed' | 'cancelled' | 'undone';

export type PipelineStatus = 'idle' | 'running' | 'paused' | 'error';

export type VariantTier = 'mini_parwa' | 'parwa' | 'parwa_high';

// ── CC Session ──────────────────────────────────────────────────────

export interface JarvisCCSession {
  id: string;
  type: 'customer_care';
  context: Record<string, unknown>;
  message_count_today: number;
  total_message_count: number;
  remaining_today: number;
  is_active: boolean;
  variant_tier: VariantTier;
  industry: string | null;
  awareness_enabled: boolean;
  pipeline_status: PipelineStatus;
  created_at: string | null;
  updated_at: string | null;
}

// ── CC Messages ─────────────────────────────────────────────────────

export interface JarvisCCMessage {
  id: string;
  session_id: string;
  role: 'user' | 'jarvis' | 'system';
  content: string;
  message_type: CCMessageType;
  metadata: Record<string, unknown>;
  pipeline_metadata?: PipelineMetadata | null;
  timestamp: string | null;
}

export interface PipelineMetadata {
  variant_tier?: VariantTier;
  technique_used?: string;
  quality_score?: number;
  latency_ms?: number;
  tokens_used?: number;
  node_path?: string[];
  escalation_triggered?: boolean;
}

// ── CC Context ──────────────────────────────────────────────────────

export interface JarvisCCContext {
  session_id: string;
  variant_tier: VariantTier;
  variant_instance_id: string | null;
  industry: string | null;
  mode: string;
  awareness_enabled: boolean;
  pipeline_status: PipelineStatus;
  last_pipeline_metadata: PipelineMetadata | null;
  proactive_alerts: ProactiveAlert[];
  runtime: Record<string, unknown>;
  full_context: Record<string, unknown>;
}

// ── Session Health ──────────────────────────────────────────────────

export interface JarvisCCSessionHealth {
  session_id: string;
  is_active: boolean;
  messages_today: number;
  total_messages: number;
  daily_limit: number;
  daily_remaining: number;
  pipeline_status: PipelineStatus;
  last_quality_score: number | null;
  awareness_enabled: boolean;
  ai_paused: boolean;
  instance?: {
    id: string;
    status: string;
    variant_tier: VariantTier;
  } | null;
}

// ── Awareness ───────────────────────────────────────────────────────

export interface AwarenessState {
  // Plan
  current_plan: string | null;
  plan_usage_today: number | null;
  subscription_status: string | null;
  days_until_renewal: number | null;
  // System Health
  system_health: string | null;
  channel_health: Record<string, string>;
  active_alerts_count: number;
  // Ticket Volume
  ticket_volume_today: number;
  ticket_volume_avg: number;
  ticket_volume_spike: boolean;
  // Agent Pool
  active_agents: number;
  agent_pool_capacity: number;
  agent_pool_utilization: number;
  // Training
  training_running: boolean;
  training_mistake_count: number;
  training_model_version: string | null;
  // Drift & Quality
  drift_status: string | null;
  drift_score: number;
  quality_score: number;
  quality_alerts: string[];
  // Errors
  last_5_errors: Array<{
    timestamp: string;
    error: string;
    source: string;
  }>;
}

export interface AwarenessSnapshot {
  id: string;
  session_id: string;
  company_id: string;
  tick_type: TickType;
  tick_number: number;
  state: AwarenessState;
  delta_significant: boolean;
  created_at: string;
}

export interface AwarenessDelta {
  changed_fields: Record<string, { old: unknown; new: unknown }>;
  has_significant_changes: boolean;
  new_alerts: string[];
  recovered: string[];
  is_first_tick: boolean;
}

export interface AwarenessTickResult {
  snapshot_id: string;
  tick_type: TickType;
  tick_number: number;
  alerts_created: number;
  alert_ids: string[];
  system_health: string | null;
  quality_score: number;
  drift_score: number;
  delta_significant: boolean;
  total_ms: number;
}

// ── Proactive Alerts ────────────────────────────────────────────────

export interface ProactiveAlert {
  id: string;
  session_id: string;
  company_id: string;
  alert_type: string;
  severity: AlertSeverity;
  category: AlertCategory;
  title: string;
  message: string;
  details: Record<string, unknown>;
  status: AlertStatus;
  action_required: boolean;
  action_url: string | null;
  ttl_seconds: number | null;
  related_snapshot_id: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

// ── Commands ────────────────────────────────────────────────────────

export interface JarvisCommand {
  command_id: string;
  session_id: string;
  company_id: string;
  raw_input: string;
  source: CommandSource;
  status: CommandStatus;
  action: string | null;
  intent: CommandIntent | null;
  scope: string | null;
  target: string | null;
  parameters: Record<string, unknown>;
  confidence: number;
  result: Record<string, unknown>;
  execution_time_ms: number | null;
  undo_available: boolean;
  error: string | null;
  suggestion: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface QuickCommandItem {
  id: string;
  label: string;
  raw_input: string;
  action: string;
  intent: CommandIntent;
  icon: string | null;
  description: string | null;
  is_custom: boolean;
}

export interface CoPilotSuggestion {
  suggestion: string;
  suggestion_type: string;
  suggested_command: string | null;
  confidence: number;
  reasoning: string;
}

// ── API Request Types ───────────────────────────────────────────────

export interface CCSessionCreateRequest {
  existing_session_id?: string;
}

export interface CCMessageSendRequest {
  content: string;
  session_id: string;
  ticket_id?: string;
  channel?: CCChannel;
}

export interface CCContextUpdateRequest {
  awareness_enabled?: boolean;
  proactive_alerts?: Record<string, unknown>[];
  custom_fields?: Record<string, unknown>;
}

export interface AwarenessTickRequest {
  session_id: string;
  tick_type: TickType;
}

export interface CommandSendRequest {
  session_id: string;
  raw_input: string;
  source?: CommandSource;
}

export interface QuickCommandRequest {
  session_id: string;
  quick_command_id: string;
}

export interface CommandUndoRequest {
  session_id: string;
  command_id?: string;
}

export interface AlertActionRequest {
  alert_id: string;
}

export interface CustomQuickCommandAddRequest {
  session_id: string;
  label: string;
  raw_input: string;
  action: string;
  intent: CommandIntent;
  icon?: string;
  description?: string;
}

export interface CustomQuickCommandRemoveRequest {
  session_id: string;
  quick_command_id: string;
}

// ── API Response Types ──────────────────────────────────────────────

export interface CCHistoryResponse {
  messages: JarvisCCMessage[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface CommandHistoryResponse {
  commands: JarvisCommand[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface SnapshotListResponse {
  snapshots: AwarenessSnapshot[];
  total: number;
  limit: number;
  offset: number;
}

export interface AlertListResponse {
  alerts: ProactiveAlert[];
  total: number;
  limit: number;
  offset: number;
}

export interface QuickCommandListResponse {
  commands: QuickCommandItem[];
  total: number;
}

export interface CommandResponse {
  command_id: string;
  status: CommandStatus;
  action: string | null;
  intent: CommandIntent | null;
  scope: string | null;
  target: string | null;
  confidence: number;
  result: Record<string, unknown>;
  execution_time_ms: number | null;
  undo_available: boolean;
  error: string | null;
  suggestion: string | null;
}

// ── WebSocket Event Types ───────────────────────────────────────────

export interface JarvisEvent {
  event_type: 'jarvis:activity' | 'jarvis:tick' | 'jarvis:state';
  company_id: string;
  session_id?: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface JarvisActivityEvent extends JarvisEvent {
  event_type: 'jarvis:activity';
  payload: {
    alert_id: string;
    alert_type: string;
    severity: AlertSeverity;
    title: string;
    action: string;
  };
}

export interface JarvisTickEvent extends JarvisEvent {
  event_type: 'jarvis:tick';
  payload: {
    tick_number: number;
    tick_type: TickType;
    system_health: string | null;
    alerts_created: number;
    quality_score?: number;
    drift_score?: number;
  };
}

export interface JarvisStateEvent extends JarvisEvent {
  event_type: 'jarvis:state';
  payload: {
    field: string;
    old_value: unknown;
    new_value: unknown;
    change_type: string;
  };
}
