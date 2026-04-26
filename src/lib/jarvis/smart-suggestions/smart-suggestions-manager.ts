/**
 * JARVIS Smart Suggestions Manager - Week 7 (Phase 2)
 *
 * Main implementation for the Smart Suggestions system.
 * Generates intelligent suggestions based on context, patterns, and user behavior.
 */

import type { Variant } from '@/types/variant';
import type { IntentAction, EntityResult } from '@/types/command';
import {
  DEFAULT_SMART_SUGGESTIONS_CONFIG,
  SMART_SUGGESTIONS_VARIANT_LIMITS,
} from './types';
import type {
  Suggestion,
  SuggestionType,
  SuggestionPriority,
  SuggestionTrigger,
  SuggestedAction,
  SuggestionContext,
  SuggestionRule,
  SuggestionCondition,
  SuggestionStats,
  SuggestionSummary,
  SuggestionEvent,
  SuggestionEventType,
  SmartSuggestionsConfig,
  SmartSuggestionsVariantLimits,
  GetSuggestionsRequest,
  GetSuggestionsResponse,
  FeedbackRequest,
  FeedbackResponse,
  UserState,
} from './types';

// ── Event Emitter ─────────────────────────────────────────────────────

type EventCallback = (event: SuggestionEvent) => void;

class SuggestionEventEmitter {
  private listeners: Map<SuggestionEventType, Set<EventCallback>> = new Map();

  on(event: SuggestionEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    return () => this.listeners.get(event)?.delete(callback);
  }

  emit(event: SuggestionEvent): void {
    const callbacks = this.listeners.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          callback(event);
        } catch (error) {
          console.error('Suggestion event callback error:', error);
        }
      }
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ── Context Tracker ────────────────────────────────────────────────────

interface ContextSnapshot {
  context: SuggestionContext;
  timestamp: Date;
  intents: Array<{ intent: IntentAction; timestamp: Date }>;
  entities: Array<{ entity: EntityResult; timestamp: Date }>;
}

class ContextTracker {
  private snapshots: Map<string, ContextSnapshot> = new Map();
  private intentHistory: Map<string, Array<{ intent: IntentAction; timestamp: Date }>> = new Map();
  private entityHistory: Map<string, Array<{ entity: EntityResult; timestamp: Date }>> = new Map();
  private retentionMs: number;

  constructor(retentionMinutes: number = 60) {
    this.retentionMs = retentionMinutes * 60 * 1000;
  }

  updateContext(userId: string, updates: Partial<SuggestionContext>): SuggestionContext {
    const existing = this.snapshots.get(userId);
    const now = new Date();

    const newContext: SuggestionContext = {
      ...existing?.context,
      ...updates,
    };

    this.snapshots.set(userId, {
      context: newContext,
      timestamp: now,
      intents: existing?.intents || [],
      entities: existing?.entities || [],
    });

    return newContext;
  }

  recordIntent(userId: string, intent: IntentAction): void {
    if (!this.intentHistory.has(userId)) {
      this.intentHistory.set(userId, []);
    }
    this.intentHistory.get(userId)!.push({ intent, timestamp: new Date() });
    this.cleanupHistory(userId);
  }

  recordEntity(userId: string, entity: EntityResult): void {
    if (!this.entityHistory.has(userId)) {
      this.entityHistory.set(userId, []);
    }
    this.entityHistory.get(userId)!.push({ entity, timestamp: new Date() });
    this.cleanupHistory(userId);
  }

  getContext(userId: string): SuggestionContext | undefined {
    return this.snapshots.get(userId)?.context;
  }

  getRecentIntents(userId: string, limit: number = 5): IntentAction[] {
    const history = this.intentHistory.get(userId) || [];
    return history.slice(-limit).map(h => h.intent);
  }

  getRecentEntities(userId: string, limit: number = 10): EntityResult[] {
    const history = this.entityHistory.get(userId) || [];
    return history.slice(-limit).map(h => h.entity);
  }

  clear(userId: string): void {
    this.snapshots.delete(userId);
    this.intentHistory.delete(userId);
    this.entityHistory.delete(userId);
  }

  private cleanupHistory(userId: string): void {
    const cutoff = new Date(Date.now() - this.retentionMs);

    const intents = this.intentHistory.get(userId);
    if (intents) {
      const filtered = intents.filter(h => h.timestamp > cutoff);
      this.intentHistory.set(userId, filtered);
    }

    const entities = this.entityHistory.get(userId);
    if (entities) {
      const filtered = entities.filter(h => h.timestamp > cutoff);
      this.entityHistory.set(userId, filtered);
    }
  }
}

// ── Suggestion Generator ───────────────────────────────────────────────

class SuggestionGenerator {
  private rules: Map<string, SuggestionRule> = new Map();
  private templates: Map<SuggestionType, Array<{
    title: string;
    description: string;
    action: SuggestedAction;
    priority: SuggestionPriority;
    conditions: (context: SuggestionContext) => boolean;
  }>> = new Map();

  constructor() {
    this.initializeTemplates();
  }

  generate(
    context: SuggestionContext,
    variantLimits: SmartSuggestionsVariantLimits,
    patterns: Suggestion[] = []
  ): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Generate context-based suggestions
    suggestions.push(...this.generateContextSuggestions(context, variantLimits));

    // Generate entity-based suggestions
    suggestions.push(...this.generateEntitySuggestions(context, variantLimits));

    // Generate time-based suggestions
    suggestions.push(...this.generateTimeSuggestions(context, variantLimits));

    // Generate workflow suggestions
    suggestions.push(...this.generateWorkflowSuggestions(context, variantLimits));

    // Add pattern-based suggestions
    if (variantLimits.pattern_suggestions) {
      suggestions.push(...patterns);
    }

    // Sort by relevance and confidence
    suggestions.sort((a, b) => {
      const relevanceDiff = b.relevance_score - a.relevance_score;
      if (relevanceDiff !== 0) return relevanceDiff;
      return b.confidence - a.confidence;
    });

    return suggestions;
  }

  private generateContextSuggestions(
    context: SuggestionContext,
    limits: SmartSuggestionsVariantLimits
  ): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Check for ticket page context
    if (context.page?.includes('ticket')) {
      suggestions.push(this.createSuggestion(
        'context',
        'proactive',
        'View Ticket Details',
        'View complete information for this ticket including history and related tickets.',
        {
          type: 'navigation',
          target: `/tickets/${context.entity_id}`,
        },
        0.85,
        'high',
        context
      ));
    }

    // Check for dashboard context
    if (context.page?.includes('dashboard')) {
      suggestions.push(this.createSuggestion(
        'context',
        'proactive',
        'Check Today\'s SLA Status',
        'Review tickets approaching SLA deadline and take action.',
        {
          type: 'command',
          intent: 'check_sla_status',
          params: { time_range: 'today' },
        },
        0.8,
        'high',
        context
      ));
    }

    // Check for customer context
    if (context.entity_type === 'customer' && context.entity_id) {
      suggestions.push(this.createSuggestion(
        'entity',
        'entity_focus',
        'View Customer History',
        'View complete interaction history for this customer.',
        {
          type: 'command',
          intent: 'view_customer_history',
          params: { customer_id: context.entity_id },
        },
        0.9,
        'high',
        context
      ));
    }

    // Check user state for workload-based suggestions
    if (context.user_state?.current_workload === 'high') {
      suggestions.push(this.createSuggestion(
        'optimization',
        'proactive',
        'Prioritize Your Queue',
        'You have high workload. Let me help prioritize your tickets.',
        {
          type: 'command',
          intent: 'prioritize_tickets',
        },
        0.75,
        'medium',
        context
      ));
    }

    return suggestions.filter(s => limits.enabled);
  }

  private generateEntitySuggestions(
    context: SuggestionContext,
    limits: SmartSuggestionsVariantLimits
  ): Suggestion[] {
    const suggestions: Suggestion[] = [];

    if (context.recent_entities && context.recent_entities.length > 0) {
      const recentEntity = context.recent_entities[context.recent_entities.length - 1];

      // Suggest actions based on entity type
      switch (recentEntity.type) {
        case 'ticket':
          suggestions.push(this.createSuggestion(
            'entity',
            'entity_focus',
            'Update Ticket Status',
            'Change the status of this ticket.',
            {
              type: 'command',
              intent: 'update_ticket',
              params: { ticket_id: recentEntity.value },
            },
            0.8,
            'medium',
            context
          ));
          break;

        case 'customer':
          suggestions.push(this.createSuggestion(
            'entity',
            'entity_focus',
            'Create New Ticket for Customer',
            'Create a new support ticket for this customer.',
            {
              type: 'command',
              intent: 'create_ticket',
              params: { customer_id: recentEntity.value },
            },
            0.75,
            'medium',
            context
          ));
          break;

        case 'agent':
          suggestions.push(this.createSuggestion(
            'collaboration',
            'entity_focus',
            'View Agent Workload',
            'Check this agent\'s current workload and availability.',
            {
              type: 'command',
              intent: 'view_agent_workload',
              params: { agent_id: recentEntity.value },
            },
            0.7,
            'low',
            context
          ));
          break;
      }
    }

    return suggestions;
  }

  private generateTimeSuggestions(
    context: SuggestionContext,
    limits: SmartSuggestionsVariantLimits
  ): Suggestion[] {
    const suggestions: Suggestion[] = [];
    const hour = new Date().getHours();

    // Morning suggestions (8-10 AM)
    if (hour >= 8 && hour < 10) {
      suggestions.push(this.createSuggestion(
        'time',
        'time_event',
        'Morning Briefing',
        'Start your day with a summary of overnight tickets and priorities.',
        {
          type: 'command',
          intent: 'daily_briefing',
          params: { type: 'morning' },
        },
        0.7,
        'medium',
        context
      ));
    }

    // End of day suggestions (5-6 PM)
    if (hour >= 17 && hour < 18) {
      suggestions.push(this.createSuggestion(
        'time',
        'time_event',
        'End of Day Summary',
        'Review your day and prepare handover notes.',
        {
          type: 'command',
          intent: 'daily_summary',
          params: { type: 'eod' },
        },
        0.65,
        'low',
        context
      ));
    }

    // SLA check suggestion (before lunch)
    if (hour >= 11 && hour < 12) {
      suggestions.push(this.createSuggestion(
        'time',
        'time_event',
        'Mid-day SLA Check',
        'Review tickets that need attention before end of day.',
        {
          type: 'command',
          intent: 'check_sla_status',
          params: { urgent_only: true },
        },
        0.6,
        'medium',
        context
      ));
    }

    return suggestions;
  }

  private generateWorkflowSuggestions(
    context: SuggestionContext,
    limits: SmartSuggestionsVariantLimits
  ): Suggestion[] {
    const suggestions: Suggestion[] = [];

    // Based on recent intents, suggest workflow completions
    if (context.recent_intents && context.recent_intents.length > 0) {
      const lastIntent = context.recent_intents[context.recent_intents.length - 1];

      // After creating a ticket, suggest assigning it
      if (lastIntent === 'create_ticket') {
        suggestions.push(this.createSuggestion(
          'workflow',
          'pattern_match',
          'Assign New Ticket',
          'Assign the newly created ticket to an available agent.',
          {
            type: 'command',
            intent: 'assign_ticket',
          },
          0.85,
          'high',
          context
        ));
      }

      // After escalating, suggest follow-up
      if (lastIntent === 'escalate_ticket') {
        suggestions.push(this.createSuggestion(
          'workflow',
          'pattern_match',
          'Set Escalation Reminder',
          'Set a reminder to follow up on this escalation.',
          {
            type: 'command',
            intent: 'set_reminder',
            params: { type: 'escalation_follow_up' },
          },
          0.8,
          'medium',
          context
        ));
      }

      // After resolving a ticket, suggest feedback request
      if (lastIntent === 'resolve_ticket') {
        suggestions.push(this.createSuggestion(
          'workflow',
          'pattern_match',
          'Send Satisfaction Survey',
          'Send a customer satisfaction survey for the resolved ticket.',
          {
            type: 'command',
            intent: 'send_survey',
            params: { type: 'satisfaction' },
          },
          0.7,
          'low',
          context
        ));
      }
    }

    return suggestions;
  }

  private createSuggestion(
    type: SuggestionType,
    trigger: SuggestionTrigger,
    title: string,
    description: string,
    action: SuggestedAction,
    confidence: number,
    priority: SuggestionPriority,
    context: SuggestionContext
  ): Suggestion {
    return {
      id: `sug_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      trigger,
      title,
      description,
      action,
      confidence,
      priority,
      relevance_score: this.calculateRelevance(type, context),
      context,
      metadata: {
        source: 'rules',
        reason: `Generated based on ${trigger} trigger and ${type} context`,
      },
      created_at: new Date(),
      dismissed: false,
      accepted: false,
    };
  }

  private calculateRelevance(type: SuggestionType, context: SuggestionContext): number {
    let relevance = 0.5; // Base relevance

    // Increase relevance for entity-focused context
    if (context.entity_id && type === 'entity') {
      relevance += 0.3;
    }

    // Increase relevance for matching recent intents
    if (context.recent_intents && context.recent_intents.length > 0) {
      relevance += 0.1;
    }

    // Increase relevance for high workload
    if (context.user_state?.current_workload === 'high') {
      relevance += 0.1;
    }

    return Math.min(1, relevance);
  }

  private initializeTemplates(): void {
    // Templates are used internally for quick suggestion generation
    // This can be extended with custom templates per tenant
  }

  addRule(rule: SuggestionRule): void {
    this.rules.set(rule.id, rule);
  }

  removeRule(ruleId: string): boolean {
    return this.rules.delete(ruleId);
  }

  getRules(): SuggestionRule[] {
    return Array.from(this.rules.values());
  }
}

// ── Feedback Learner ───────────────────────────────────────────────────

class FeedbackLearner {
  private feedbackHistory: Map<string, Array<{
    type: SuggestionType;
    accepted: boolean;
    timestamp: Date;
  }>> = new Map();

  private typeWeights: Map<SuggestionType, number> = new Map();

  recordFeedback(
    userId: string,
    suggestionType: SuggestionType,
    accepted: boolean
  ): void {
    if (!this.feedbackHistory.has(userId)) {
      this.feedbackHistory.set(userId, []);
    }

    this.feedbackHistory.get(userId)!.push({
      type: suggestionType,
      accepted,
      timestamp: new Date(),
    });

    this.updateWeights(userId);
  }

  getAdjustedConfidence(
    userId: string,
    suggestionType: SuggestionType,
    baseConfidence: number
  ): number {
    const weight = this.typeWeights.get(suggestionType) ?? 1;
    return Math.min(1, Math.max(0, baseConfidence * weight));
  }

  getTypePreferences(userId: string): Map<SuggestionType, number> {
    const history = this.feedbackHistory.get(userId) || [];
    const typeStats = new Map<SuggestionType, { accepted: number; total: number }>();

    for (const feedback of history) {
      const stats = typeStats.get(feedback.type) || { accepted: 0, total: 0 };
      stats.total++;
      if (feedback.accepted) stats.accepted++;
      typeStats.set(feedback.type, stats);
    }

    const preferences = new Map<SuggestionType, number>();
    for (const [type, stats] of typeStats) {
      preferences.set(type, stats.total > 0 ? stats.accepted / stats.total : 0.5);
    }

    return preferences;
  }

  private updateWeights(userId: string): void {
    const preferences = this.getTypePreferences(userId);
    for (const [type, rate] of preferences) {
      // Weight ranges from 0.5 to 1.5 based on acceptance rate
      this.typeWeights.set(type, 0.5 + rate);
    }
  }
}

// ── Smart Suggestions Manager ───────────────────────────────────────────

export class SmartSuggestionsManager {
  private config: SmartSuggestionsConfig;
  private variantLimits: SmartSuggestionsVariantLimits;
  private generator: SuggestionGenerator;
  private contextTracker: ContextTracker;
  private feedbackLearner: FeedbackLearner;
  private eventEmitter: SuggestionEventEmitter;
  private suggestions: Map<string, Suggestion> = new Map();
  private suggestionsByUser: Map<string, Set<string>> = new Map();
  private stats = {
    totalGenerated: 0,
    totalAccepted: 0,
    totalDismissed: 0,
    byType: new Map<SuggestionType, number>(),
    byTrigger: new Map<SuggestionTrigger, number>(),
  };

  constructor(config: SmartSuggestionsConfig) {
    this.config = { ...DEFAULT_SMART_SUGGESTIONS_CONFIG, ...config } as SmartSuggestionsConfig;
    this.variantLimits = SMART_SUGGESTIONS_VARIANT_LIMITS[config.variant];
    this.generator = new SuggestionGenerator();
    this.contextTracker = new ContextTracker(this.config.context_tracking.retention_minutes);
    this.feedbackLearner = new FeedbackLearner();
    this.eventEmitter = new SuggestionEventEmitter();
  }

  // ── Context Management ─────────────────────────────────────────────

  updateContext(userId: string, context: Partial<SuggestionContext>): void {
    if (!this.variantLimits.enabled) return;

    // Track intents
    if (context.recent_intents && context.recent_intents.length > 0) {
      const newIntent = context.recent_intents[context.recent_intents.length - 1];
      if (newIntent) {
        this.contextTracker.recordIntent(userId, newIntent);
      }
    }

    // Track entities
    if (context.recent_entities && context.recent_entities.length > 0) {
      const newEntity = context.recent_entities[context.recent_entities.length - 1];
      if (newEntity) {
        this.contextTracker.recordEntity(userId, newEntity);
      }
    }

    this.contextTracker.updateContext(userId, context);
  }

  getContext(userId: string): SuggestionContext | undefined {
    return this.contextTracker.getContext(userId);
  }

  // ── Suggestion Generation ───────────────────────────────────────────

  getSuggestions(request: GetSuggestionsRequest): GetSuggestionsResponse {
    const startTime = Date.now();

    if (!this.variantLimits.enabled) {
      return {
        suggestions: [],
        context_used: request.context,
        generation_time_ms: 0,
      };
    }

    // Merge with tracked context
    const trackedContext = this.contextTracker.getContext(request.user_id);
    const mergedContext: SuggestionContext = {
      ...trackedContext,
      ...request.context,
      recent_intents: this.contextTracker.getRecentIntents(request.user_id),
      recent_entities: this.contextTracker.getRecentEntities(request.user_id),
    };

    // Generate suggestions
    let suggestions = this.generator.generate(
      mergedContext,
      this.variantLimits
    );

    // Filter by types if specified
    if (request.types && request.types.length > 0) {
      suggestions = suggestions.filter(s => request.types!.includes(s.type));
    }

    // Filter by confidence threshold
    suggestions = suggestions.filter(
      s => s.confidence >= this.config.min_confidence_threshold
    );

    // Apply learned adjustments
    suggestions = suggestions.map(s => ({
      ...s,
      confidence: this.feedbackLearner.getAdjustedConfidence(
        request.user_id,
        s.type,
        s.confidence
      ),
    }));

    // Re-filter after confidence adjustment
    suggestions = suggestions.filter(
      s => s.confidence >= this.config.min_confidence_threshold
    );

    // Apply limit
    const limit = request.limit ?? this.config.max_suggestions_per_context;
    suggestions = suggestions.slice(0, limit);

    // Store suggestions
    for (const suggestion of suggestions) {
      this.storeSuggestion(request.user_id, request.tenant_id, suggestion);
    }

    // Update stats
    this.updateStats(suggestions);

    // Emit events
    for (const suggestion of suggestions) {
      this.emitEvent('suggestion_generated', request.user_id, request.tenant_id, {
        suggestion_id: suggestion.id,
        type: suggestion.type,
      });
    }

    return {
      suggestions,
      context_used: mergedContext,
      generation_time_ms: Date.now() - startTime,
    };
  }

  getSuggestion(suggestionId: string): Suggestion | undefined {
    return this.suggestions.get(suggestionId);
  }

  // ── Feedback Handling ───────────────────────────────────────────────

  submitFeedback(request: FeedbackRequest): FeedbackResponse {
    const suggestion = this.suggestions.get(request.suggestion_id);

    if (!suggestion) {
      return {
        success: false,
        learning_applied: false,
        message: 'Suggestion not found',
      };
    }

    // Update suggestion state
    if (request.feedback === 'accepted') {
      suggestion.accepted = true;
      this.stats.totalAccepted++;
    } else if (request.feedback === 'dismissed') {
      suggestion.dismissed = true;
      this.stats.totalDismissed++;
    }

    // Apply learning
    if (this.variantLimits.learning_enabled && this.config.learning_enabled) {
      this.feedbackLearner.recordFeedback(
        request.user_id,
        suggestion.type,
        request.feedback === 'accepted'
      );
    }

    // Emit event
    const eventType: SuggestionEventType =
      request.feedback === 'accepted' ? 'suggestion_accepted' : 'suggestion_dismissed';
    this.emitEvent(eventType, request.user_id, request.tenant_id, {
      suggestion_id: request.suggestion_id,
      feedback: request.feedback,
    });

    return {
      success: true,
      learning_applied: this.variantLimits.learning_enabled,
      message: 'Feedback recorded successfully',
    };
  }

  // ── Rule Management ─────────────────────────────────────────────────

  addRule(rule: SuggestionRule): boolean {
    if (!this.variantLimits.custom_rules) {
      return false;
    }

    // Check rule limit
    const currentRules = this.generator.getRules();
    if (currentRules.length >= this.variantLimits.max_custom_rules) {
      return false;
    }

    // Check variant filter
    if (rule.variant_filter && !rule.variant_filter.includes(this.config.variant)) {
      return false;
    }

    this.generator.addRule(rule);
    this.emitEvent('rule_added', '', this.config.tenant_id, { rule_id: rule.id });
    return true;
  }

  updateRule(ruleId: string, updates: Partial<SuggestionRule>): SuggestionRule | undefined {
    const existing = this.generator.getRules().find(r => r.id === ruleId);
    if (!existing) return undefined;

    const updated: SuggestionRule = {
      ...existing,
      ...updates,
      updated_at: new Date(),
    };

    this.generator.addRule(updated);
    this.emitEvent('rule_updated', '', this.config.tenant_id, { rule_id: ruleId });
    return updated;
  }

  deleteRule(ruleId: string): boolean {
    const result = this.generator.removeRule(ruleId);
    if (result) {
      this.emitEvent('rule_deleted', '', this.config.tenant_id, { rule_id: ruleId });
    }
    return result;
  }

  getRules(): SuggestionRule[] {
    return this.generator.getRules();
  }

  // ── Statistics ──────────────────────────────────────────────────────

  getStats(): SuggestionStats {
    const total = this.stats.totalGenerated;
    const acceptanceRate = total > 0 ? this.stats.totalAccepted / total : 0;
    const dismissalRate = total > 0 ? this.stats.totalDismissed / total : 0;

    // Calculate average confidence
    let totalConfidence = 0;
    let count = 0;
    for (const suggestion of this.suggestions.values()) {
      totalConfidence += suggestion.confidence;
      count++;
    }

    const byType: Record<SuggestionType, number> = {
      command: 0,
      workflow: 0,
      entity: 0,
      context: 0,
      time: 0,
      pattern: 0,
      collaboration: 0,
      optimization: 0,
    };

    for (const [type, count] of this.stats.byType) {
      byType[type] = count;
    }

    const byTrigger: Record<SuggestionTrigger, number> = {
      explicit_request: 0,
      context_change: 0,
      time_event: 0,
      pattern_match: 0,
      entity_focus: 0,
      anomaly_detected: 0,
      proactive: 0,
    };

    for (const [trigger, count] of this.stats.byTrigger) {
      byTrigger[trigger] = count;
    }

    return {
      total_suggestions_generated: total,
      suggestions_by_type: byType,
      suggestions_by_trigger: byTrigger,
      acceptance_rate: acceptanceRate,
      dismissal_rate: dismissalRate,
      average_confidence: count > 0 ? totalConfidence / count : 0,
      top_suggestions: this.getTopSuggestions(),
      variant_stats: {
        [this.config.variant]: {
          total_generated: total,
          acceptance_rate: acceptanceRate,
          max_suggestions_per_day: this.variantLimits.max_suggestions_per_hour * 24,
          types_available: Object.keys(byType).filter(
            t => byType[t as SuggestionType] > 0
          ) as SuggestionType[],
        },
      },
    };
  }

  private getTopSuggestions(): SuggestionSummary[] {
    const summaries = new Map<string, SuggestionSummary>();

    for (const suggestion of this.suggestions.values()) {
      const key = `${suggestion.type}:${suggestion.title}`;
      const existing = summaries.get(key) || {
        type: suggestion.type,
        title: suggestion.title,
        acceptance_count: 0,
        dismissal_count: 0,
        acceptance_rate: 0,
      };

      if (suggestion.accepted) existing.acceptance_count++;
      if (suggestion.dismissed) existing.dismissal_count++;

      const total = existing.acceptance_count + existing.dismissal_count;
      existing.acceptance_rate = total > 0 ? existing.acceptance_count / total : 0;

      summaries.set(key, existing);
    }

    return Array.from(summaries.values())
      .sort((a, b) => b.acceptance_rate - a.acceptance_rate)
      .slice(0, 10);
  }

  // ── Events ──────────────────────────────────────────────────────────

  onEvent(event: SuggestionEventType, callback: (event: SuggestionEvent) => void): () => void {
    return this.eventEmitter.on(event, callback);
  }

  // ── Lifecycle ───────────────────────────────────────────────────────

  shutdown(): void {
    this.suggestions.clear();
    this.suggestionsByUser.clear();
    this.eventEmitter.clear();
  }

  // ── Private Methods ────────────────────────────────────────────────

  private storeSuggestion(userId: string, tenantId: string, suggestion: Suggestion): void {
    this.suggestions.set(suggestion.id, suggestion);

    if (!this.suggestionsByUser.has(userId)) {
      this.suggestionsByUser.set(userId, new Set());
    }
    this.suggestionsByUser.get(userId)!.add(suggestion.id);
  }

  private updateStats(suggestions: Suggestion[]): void {
    for (const suggestion of suggestions) {
      this.stats.totalGenerated++;

      const typeCount = this.stats.byType.get(suggestion.type) || 0;
      this.stats.byType.set(suggestion.type, typeCount + 1);

      const triggerCount = this.stats.byTrigger.get(suggestion.trigger) || 0;
      this.stats.byTrigger.set(suggestion.trigger, triggerCount + 1);
    }
  }

  private emitEvent(
    type: SuggestionEventType,
    userId: string,
    tenantId: string,
    metadata?: Record<string, unknown>
  ): void {
    // Extract suggestion_id and rule_id from metadata to put at top level
    const suggestion_id = metadata?.suggestion_id as string | undefined;
    const rule_id = metadata?.rule_id as string | undefined;

    // Create a clean metadata object without the extracted fields
    const cleanMetadata = { ...metadata };
    delete cleanMetadata.suggestion_id;
    delete cleanMetadata.rule_id;

    this.eventEmitter.emit({
      type,
      suggestion_id,
      rule_id,
      user_id: userId,
      tenant_id: tenantId,
      timestamp: new Date(),
      metadata: Object.keys(cleanMetadata).length > 0 ? cleanMetadata : undefined,
    });
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createSmartSuggestionsManager(
  config: SmartSuggestionsConfig
): SmartSuggestionsManager {
  return new SmartSuggestionsManager(config);
}

// ── Singleton Registry ────────────────────────────────────────────────

const managers = new Map<string, SmartSuggestionsManager>();

export function getSmartSuggestionsManager(
  tenantId: string,
  variant: Variant
): SmartSuggestionsManager {
  const key = `${tenantId}:${variant}`;

  if (!managers.has(key)) {
    managers.set(key, createSmartSuggestionsManager({
      tenant_id: tenantId,
      variant,
    }));
  }

  return managers.get(key)!;
}

export function shutdownSmartSuggestionsManager(tenantId: string, variant: Variant): void {
  const key = `${tenantId}:${variant}`;
  const manager = managers.get(key);
  if (manager) {
    manager.shutdown();
    managers.delete(key);
  }
}
