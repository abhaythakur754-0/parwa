/**
 * JARVIS Smart Suggestions Types - Week 7 (Phase 2)
 *
 * Type definitions for the Smart Suggestions system.
 * Provides intelligent recommendations based on context, patterns, and user behavior.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction, EntityResult } from '@/types/command';

// ── Suggestion Types ───────────────────────────────────────────────────

export type SuggestionType =
  | 'command'           // Command suggestions (e.g., "show tickets")
  | 'workflow'          // Workflow suggestions (e.g., "escalate ticket")
  | 'entity'            // Entity-related suggestions (e.g., "view customer details")
  | 'context'           // Context-based suggestions (e.g., "check SLA")
  | 'time'              // Time-based suggestions (e.g., "morning report")
  | 'pattern'           // Pattern-based suggestions from learned behavior
  | 'collaboration'     // Team collaboration suggestions
  | 'optimization';     // Performance optimization suggestions

export type SuggestionPriority = 'critical' | 'high' | 'medium' | 'low';

export type SuggestionTrigger =
  | 'explicit_request'  // User explicitly asked for suggestions
  | 'context_change'    // Context changed (page, ticket, etc.)
  | 'time_event'        // Scheduled time event
  | 'pattern_match'     // User behavior pattern matched
  | 'entity_focus'      // User focused on an entity
  | 'anomaly_detected'  // Anomaly in metrics detected
  | 'proactive';        // Proactive suggestion (no specific trigger)

// ── Base Suggestion ────────────────────────────────────────────────────

export interface Suggestion {
  id: string;
  type: SuggestionType;
  trigger: SuggestionTrigger;
  title: string;
  description: string;
  action: SuggestedAction;
  confidence: number;              // 0-1 confidence score
  priority: SuggestionPriority;
  relevance_score: number;         // 0-1 relevance to current context
  context: SuggestionContext;
  metadata: SuggestionMetadata;
  created_at: Date;
  expires_at?: Date;
  dismissed: boolean;
  accepted: boolean;
}

export interface SuggestedAction {
  type: 'command' | 'navigation' | 'api_call' | 'workflow' | 'notification';
  intent?: IntentAction;
  params?: Record<string, unknown>;
  target?: string;                 // URL, entity ID, etc.
  workflow_id?: string;
  api_endpoint?: string;
  api_method?: string;
  api_payload?: Record<string, unknown>;
}

export interface SuggestionContext {
  page?: string;
  entity_type?: string;
  entity_id?: string;
  conversation_context?: string;
  recent_intents?: IntentAction[];
  recent_entities?: EntityResult[];
  time_of_day?: 'morning' | 'afternoon' | 'evening' | 'night';
  day_of_week?: string;
  active_tickets?: string[];
  user_state?: UserState;
}

export interface UserState {
  current_workload: 'low' | 'medium' | 'high';
  focus_mode: boolean;
  pending_actions: number;
  last_action?: Date;
  session_duration_minutes?: number;
}

export interface SuggestionMetadata {
  source: 'pattern_learning' | 'rules' | 'ml_model' | 'collaboration' | 'optimization';
  reason: string;
  supporting_data?: Record<string, unknown>;
  variant_restricted?: boolean;
  tags?: string[];
}

// ── Suggestion Rules ────────────────────────────────────────────────────

export interface SuggestionRule {
  id: string;
  name: string;
  description: string;
  type: SuggestionType;
  priority: SuggestionPriority;
  conditions: SuggestionCondition[];
  action: SuggestedAction;
  enabled: boolean;
  variant_filter?: Variant[];
  tenant_filter?: string[];
  created_at: Date;
  updated_at: Date;
}

export interface SuggestionCondition {
  type: 'context' | 'entity' | 'time' | 'intent' | 'metric' | 'state';
  field: string;
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'in' | 'matches';
  value: unknown;
}

// ── Suggestion Templates ───────────────────────────────────────────────

export interface SuggestionTemplate {
  id: string;
  type: SuggestionType;
  title_template: string;
  description_template: string;
  action_template: Partial<SuggestedAction>;
  priority: SuggestionPriority;
  min_confidence: number;
  triggers: SuggestionTrigger[];
}

// ── Suggestion Statistics ───────────────────────────────────────────────

export interface SuggestionStats {
  total_suggestions_generated: number;
  suggestions_by_type: Record<SuggestionType, number>;
  suggestions_by_trigger: Record<SuggestionTrigger, number>;
  acceptance_rate: number;
  dismissal_rate: number;
  average_confidence: number;
  top_suggestions: SuggestionSummary[];
  variant_stats: Record<Variant, VariantSuggestionStats>;
}

export interface SuggestionSummary {
  type: SuggestionType;
  title: string;
  acceptance_count: number;
  dismissal_count: number;
  acceptance_rate: number;
}

export interface VariantSuggestionStats {
  total_generated: number;
  acceptance_rate: number;
  max_suggestions_per_day: number;
  types_available: SuggestionType[];
}

// ── Configuration ───────────────────────────────────────────────────────

export interface SmartSuggestionsConfig {
  tenant_id: string;
  variant: Variant;
  enabled: boolean;
  max_suggestions_per_context: number;
  min_confidence_threshold: number;
  cooldown_minutes: number;          // Min time between similar suggestions
  learning_enabled: boolean;
  rules: SuggestionRuleConfig[];
  context_tracking: ContextTrackingConfig;
}

export interface SuggestionRuleConfig {
  type: SuggestionType;
  enabled: boolean;
  min_confidence: number;
  max_per_hour: number;
}

export interface ContextTrackingConfig {
  track_page_changes: boolean;
  track_entity_focus: boolean;
  track_intents: boolean;
  track_time_patterns: boolean;
  retention_minutes: number;
}

export const DEFAULT_SMART_SUGGESTIONS_CONFIG: Omit<SmartSuggestionsConfig, 'tenant_id' | 'variant'> = {
  enabled: true,
  max_suggestions_per_context: 5,
  min_confidence_threshold: 0.6,
  cooldown_minutes: 30,
  learning_enabled: true,
  rules: [
    { type: 'command', enabled: true, min_confidence: 0.7, max_per_hour: 10 },
    { type: 'workflow', enabled: true, min_confidence: 0.75, max_per_hour: 5 },
    { type: 'entity', enabled: true, min_confidence: 0.65, max_per_hour: 15 },
    { type: 'context', enabled: true, min_confidence: 0.6, max_per_hour: 10 },
    { type: 'time', enabled: true, min_confidence: 0.5, max_per_hour: 3 },
    { type: 'pattern', enabled: true, min_confidence: 0.8, max_per_hour: 5 },
    { type: 'collaboration', enabled: true, min_confidence: 0.7, max_per_hour: 3 },
    { type: 'optimization', enabled: true, min_confidence: 0.65, max_per_hour: 5 },
  ],
  context_tracking: {
    track_page_changes: true,
    track_entity_focus: true,
    track_intents: true,
    track_time_patterns: true,
    retention_minutes: 60,
  },
};

// ── Variant Limits ──────────────────────────────────────────────────────

export interface SmartSuggestionsVariantLimits {
  enabled: boolean;
  max_suggestions_per_hour: number;
  learning_enabled: boolean;
  pattern_suggestions: boolean;
  collaboration_suggestions: boolean;
  optimization_suggestions: boolean;
  custom_rules: boolean;
  max_custom_rules: number;
}

export const SMART_SUGGESTIONS_VARIANT_LIMITS: Record<Variant, SmartSuggestionsVariantLimits> = {
  mini_parwa: {
    enabled: true,
    max_suggestions_per_hour: 5,
    learning_enabled: false,
    pattern_suggestions: false,
    collaboration_suggestions: false,
    optimization_suggestions: false,
    custom_rules: false,
    max_custom_rules: 0,
  },
  parwa: {
    enabled: true,
    max_suggestions_per_hour: 20,
    learning_enabled: true,
    pattern_suggestions: true,
    collaboration_suggestions: true,
    optimization_suggestions: false,
    custom_rules: true,
    max_custom_rules: 10,
  },
  parwa_high: {
    enabled: true,
    max_suggestions_per_hour: -1, // Unlimited
    learning_enabled: true,
    pattern_suggestions: true,
    collaboration_suggestions: true,
    optimization_suggestions: true,
    custom_rules: true,
    max_custom_rules: 50,
  },
};

// ── Suggestion Events ───────────────────────────────────────────────────

export type SuggestionEventType =
  | 'suggestion_generated'
  | 'suggestion_presented'
  | 'suggestion_accepted'
  | 'suggestion_dismissed'
  | 'suggestion_expired'
  | 'rule_added'
  | 'rule_updated'
  | 'rule_deleted';

export interface SuggestionEvent {
  type: SuggestionEventType;
  suggestion_id?: string;
  rule_id?: string;
  user_id: string;
  tenant_id: string;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

// ── Request/Response Types ──────────────────────────────────────────────

export interface GetSuggestionsRequest {
  tenant_id: string;
  user_id: string;
  context: SuggestionContext;
  trigger?: SuggestionTrigger;
  types?: SuggestionType[];
  limit?: number;
}

export interface GetSuggestionsResponse {
  suggestions: Suggestion[];
  context_used: SuggestionContext;
  generation_time_ms: number;
}

export interface FeedbackRequest {
  suggestion_id: string;
  feedback: 'accepted' | 'dismissed' | 'not_helpful' | 'helpful';
  user_id: string;
  tenant_id: string;
  reason?: string;
}

export interface FeedbackResponse {
  success: boolean;
  learning_applied: boolean;
  message?: string;
}
