/**
 * JARVIS Intent Classifier (Week 3 - Phase 1)
 *
 * Classifies user intents from natural language input.
 * Uses pattern matching, keyword detection, and context-aware classification.
 */

import type {
  IntentAction,
  IntentCategory,
  IntentResult,
  ConfidenceLevel,
  CommandContext,
} from '@/types/command';

// ── Intent Pattern Definitions ────────────────────────────────────────

interface IntentPattern {
  intent: IntentAction;
  category: IntentCategory;
  patterns: string[];
  keywords: string[];
  context_boosts: Record<string, number>;
  weight: number;
}

const INTENT_PATTERNS: IntentPattern[] = [
  // Ticket Creation
  {
    intent: 'create_ticket',
    category: 'ticket',
    patterns: [
      'create (a )?new ticket',
      'open (a )?ticket',
      'start (a )?new (ticket|case)',
      'I need (to )?(create|open|start) (a )?ticket',
      'new (support )?ticket',
    ],
    keywords: ['create', 'new', 'open', 'ticket', 'case', 'issue'],
    context_boosts: { page_context: { tickets_list: 0.3, customer_view: 0.2 } },
    weight: 1.0,
  },

  // Ticket View
  {
    intent: 'view_ticket',
    category: 'ticket',
    patterns: [
      '(show|view|display|get) (me )?(the )?ticket',
      'open ticket',
      'ticket details',
      'what( is|\'s) (the status of )?ticket',
    ],
    keywords: ['show', 'view', 'ticket', 'details', 'status'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // Ticket Update
  {
    intent: 'update_ticket',
    category: 'ticket',
    patterns: [
      'update (the )?ticket',
      'change (the )?ticket',
      'modify (the )?ticket',
      'edit (the )?ticket',
    ],
    keywords: ['update', 'change', 'modify', 'edit', 'ticket'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // Ticket Close
  {
    intent: 'close_ticket',
    category: 'ticket',
    patterns: [
      'close (the )?ticket',
      'resolve (the )?ticket',
      'mark (as )?(resolved|closed)',
      'complete (the )?ticket',
    ],
    keywords: ['close', 'resolve', 'complete', 'done', 'finish'],
    context_boosts: { current_ticket: 0.5 },
    weight: 1.0,
  },

  // Ticket Assign
  {
    intent: 'assign_ticket',
    category: 'ticket',
    patterns: [
      'assign (the )?ticket (to )?',
      'give (the )?ticket (to )?',
      'transfer (the )?ticket (to )?',
      'reassign (the )?ticket',
    ],
    keywords: ['assign', 'give', 'transfer', 'reassign', 'delegate'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // Ticket Escalate
  {
    intent: 'escalate_ticket',
    category: 'ticket',
    patterns: [
      'escalate (the )?ticket',
      'escalate (this|it)',
      'need escalation',
      'escalate to',
      'move to (higher|next) (level|tier)',
    ],
    keywords: ['escalate', 'escalation', 'higher', 'level', 'manager'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.1,
  },

  // Ticket Merge
  {
    intent: 'merge_tickets',
    category: 'ticket',
    patterns: [
      'merge (these|the )?tickets',
      'combine (these|the )?tickets',
      'join (these|the )?tickets',
    ],
    keywords: ['merge', 'combine', 'join', 'tickets'],
    context_boosts: {},
    weight: 1.0,
  },

  // Search Tickets
  {
    intent: 'search_tickets',
    category: 'ticket',
    patterns: [
      'search (for )?tickets',
      'find tickets',
      'show (me )?tickets',
      'list tickets',
      'get tickets (with|where|about)',
    ],
    keywords: ['search', 'find', 'show', 'list', 'tickets', 'filter'],
    context_boosts: {},
    weight: 1.0,
  },

  // Prioritize Ticket
  {
    intent: 'prioritize_ticket',
    category: 'ticket',
    patterns: [
      '(set|change|update) (the )?priority (to )?',
      'make (it|this) (high|low|urgent|critical) priority',
      'prioritize (this|the )?ticket',
    ],
    keywords: ['priority', 'urgent', 'critical', 'high', 'low', 'medium'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // Tag Ticket
  {
    intent: 'tag_ticket',
    category: 'ticket',
    patterns: [
      '(add|remove) (a )?tag (to|from )?',
      'tag (this|the )?ticket (with )?',
      'label (this|the )?ticket',
    ],
    keywords: ['tag', 'label', 'category', 'mark'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // View Customer
  {
    intent: 'view_customer',
    category: 'customer',
    patterns: [
      '(show|view|get) (me )?(the )?customer',
      'customer (profile|details|info)',
      'who is (this )?customer',
    ],
    keywords: ['customer', 'profile', 'details', 'info'],
    context_boosts: { current_customer: 0.5, current_ticket: 0.2 },
    weight: 1.0,
  },

  // Search Customer
  {
    intent: 'search_customer',
    category: 'customer',
    patterns: [
      'search (for )?(a )?customer',
      'find (a )?customer',
      'lookup customer',
    ],
    keywords: ['search', 'find', 'lookup', 'customer'],
    context_boosts: {},
    weight: 1.0,
  },

  // Customer History
  {
    intent: 'view_customer_history',
    category: 'customer',
    patterns: [
      '(show|view|get) (customer )?history',
      'past (tickets|interactions)',
      'customer(\'s)? (previous|past) (tickets|issues)',
    ],
    keywords: ['history', 'past', 'previous', 'interactions', 'tickets'],
    context_boosts: { current_customer: 0.5 },
    weight: 1.0,
  },

  // View Agent Status
  {
    intent: 'view_agent_status',
    category: 'agent',
    patterns: [
      '(show|view|get) agent status',
      'who is (available|online|busy)',
      'team status',
      'agent availability',
    ],
    keywords: ['agent', 'status', 'available', 'online', 'team', 'availability'],
    context_boosts: {},
    weight: 1.0,
  },

  // View Workload
  {
    intent: 'view_workload',
    category: 'agent',
    patterns: [
      '(show|view) (team )?workload',
      'ticket distribution',
      'who has how many tickets',
      'agent workload',
    ],
    keywords: ['workload', 'distribution', 'busy', 'tickets', 'load'],
    context_boosts: {},
    weight: 1.0,
  },

  // Generate Report
  {
    intent: 'generate_report',
    category: 'analytics',
    patterns: [
      'generate (a )?report',
      'create (a )?report',
      '(show|get) (me )?report',
      'run report',
    ],
    keywords: ['report', 'analytics', 'statistics', 'metrics'],
    context_boosts: {},
    weight: 1.0,
  },

  // View Statistics
  {
    intent: 'view_statistics',
    category: 'analytics',
    patterns: [
      '(show|view|get) (me )?(the )?statistics',
      'what are (the )?stats',
      'performance (stats|metrics)',
      'today\'s (stats|numbers)',
    ],
    keywords: ['statistics', 'stats', 'metrics', 'performance', 'numbers'],
    context_boosts: {},
    weight: 1.0,
  },

  // Export Data
  {
    intent: 'export_data',
    category: 'analytics',
    patterns: [
      'export (data|tickets|customers)',
      'download (data|report)',
      'get (a )?(csv|excel|pdf)',
    ],
    keywords: ['export', 'download', 'csv', 'excel', 'pdf'],
    context_boosts: {},
    weight: 1.0,
  },

  // Check Health
  {
    intent: 'check_health',
    category: 'system',
    patterns: [
      'system health',
      'check (system )?health',
      'is everything (ok|working)',
      'system status',
    ],
    keywords: ['health', 'status', 'system', 'ok', 'working'],
    context_boosts: {},
    weight: 1.0,
  },

  // View Alerts
  {
    intent: 'view_alerts',
    category: 'system',
    patterns: [
      '(show|view|get) (me )?(the )?alerts',
      'what alerts',
      'any alerts',
      'active alerts',
    ],
    keywords: ['alerts', 'warnings', 'notifications'],
    context_boosts: {},
    weight: 1.0,
  },

  // Acknowledge Alert
  {
    intent: 'acknowledge_alert',
    category: 'system',
    patterns: [
      'acknowledge (the )?alert',
      'dismiss (the )?alert',
      'clear (the )?alert',
    ],
    keywords: ['acknowledge', 'dismiss', 'clear', 'alert'],
    context_boosts: {},
    weight: 1.0,
  },

  // Search Knowledge
  {
    intent: 'search_knowledge',
    category: 'knowledge',
    patterns: [
      'search (the )?knowledge (base|base)',
      'find (in )?knowledge',
      'look up (in )?kb',
      'find article',
    ],
    keywords: ['knowledge', 'kb', 'article', 'documentation'],
    context_boosts: {},
    weight: 1.0,
  },

  // Suggest Response
  {
    intent: 'suggest_response',
    category: 'knowledge',
    patterns: [
      'suggest (a )?response',
      'give me (a )?reply',
      'how (should|do) I (respond|reply|answer)',
      'response suggestion',
    ],
    keywords: ['suggest', 'response', 'reply', 'answer'],
    context_boosts: { current_ticket: 0.4 },
    weight: 1.0,
  },

  // Send Message
  {
    intent: 'send_message',
    category: 'communication',
    patterns: [
      'send (a )?message (to )?',
      'reply to (customer|ticket)',
      'respond to',
    ],
    keywords: ['send', 'message', 'reply', 'respond'],
    context_boosts: { current_ticket: 0.4, current_customer: 0.3 },
    weight: 1.0,
  },

  // Schedule Followup
  {
    intent: 'schedule_followup',
    category: 'communication',
    patterns: [
      'schedule (a )?followup',
      'set (a )?reminder (to )?follow',
      'remind me (to )?follow up',
    ],
    keywords: ['schedule', 'followup', 'reminder', 'later'],
    context_boosts: { current_ticket: 0.4, current_customer: 0.3 },
    weight: 1.0,
  },

  // Create Note
  {
    intent: 'create_note',
    category: 'communication',
    patterns: [
      '(add|create|write) (a )?note',
      'note (this|that|down)',
      'internal note',
    ],
    keywords: ['note', 'internal', 'comment'],
    context_boosts: { current_ticket: 0.5 },
    weight: 1.0,
  },

  // Get Help
  {
    intent: 'get_help',
    category: 'help',
    patterns: [
      'help (me )?',
      'I need help',
      'how do I',
      'what can you do',
      'show (me )?commands',
    ],
    keywords: ['help', 'how', 'what', 'commands', 'guide'],
    context_boosts: {},
    weight: 1.0,
  },

  // List Commands
  {
    intent: 'list_commands',
    category: 'help',
    patterns: [
      'list (all )?commands',
      'show (me )?(all )?commands',
      'what commands (are )?available',
      'available commands',
    ],
    keywords: ['list', 'commands', 'available'],
    context_boosts: {},
    weight: 1.0,
  },
];

// ── Intent Classifier Class ──────────────────────────────────────────

export class IntentClassifier {
  private patterns: IntentPattern[];
  private contextHistory: Map<string, IntentResult[]> = new Map();

  constructor() {
    this.patterns = INTENT_PATTERNS;
  }

  /**
   * Classify intent from text
   */
  classify(text: string, context?: CommandContext): IntentResult {
    const normalizedText = this.normalizeText(text);
    const scores = this.calculateScores(normalizedText, context);
    const sortedIntents = this.sortByScore(scores);

    if (sortedIntents.length === 0 || sortedIntents[0].score < 0.1) {
      return this.createUnknownResult(text);
    }

    const topIntent = sortedIntents[0];
    const confidence = this.calculateConfidence(topIntent.score, sortedIntents);
    const confidenceLevel = this.getConfidenceLevel(confidence);

    const result: IntentResult = {
      intent: topIntent.intent,
      category: topIntent.category,
      confidence,
      confidence_level: confidenceLevel,
      alternative_intents: sortedIntents.slice(1, 3).map((i) => ({
        intent: i.intent,
        confidence: i.confidence,
      })),
      raw_text: text,
      normalized_text: normalizedText,
    };

    // Store in context history
    if (context?.session_id) {
      this.addToHistory(context.session_id, result);
    }

    return result;
  }

  /**
   * Get intent suggestions based on partial input
   */
  suggest(text: string, context?: CommandContext): Array<{
    intent: IntentAction;
    description: string;
    confidence: number;
  }> {
    const normalizedText = this.normalizeText(text);
    const scores = this.calculateScores(normalizedText, context);

    return scores
      .filter((s) => s.score > 0.3)
      .slice(0, 5)
      .map((s) => ({
        intent: s.intent,
        description: this.getIntentDescription(s.intent),
        confidence: s.score,
      }));
  }

  /**
   * Get intent description
   */
  getIntentDescription(intent: IntentAction): string {
    const descriptions: Record<IntentAction, string> = {
      create_ticket: 'Create a new support ticket',
      update_ticket: 'Update ticket information',
      close_ticket: 'Close or resolve a ticket',
      assign_ticket: 'Assign ticket to an agent',
      escalate_ticket: 'Escalate ticket to higher level',
      merge_tickets: 'Merge multiple tickets',
      search_tickets: 'Search for tickets',
      view_ticket: 'View ticket details',
      prioritize_ticket: 'Change ticket priority',
      tag_ticket: 'Add or remove tags from ticket',
      view_customer: 'View customer profile',
      search_customer: 'Search for customers',
      update_customer: 'Update customer information',
      merge_customers: 'Merge duplicate customers',
      view_customer_history: 'View customer history',
      view_agent_status: 'View agent availability',
      assign_to_agent: 'Assign to specific agent',
      view_workload: 'View team workload',
      reassign_tickets: 'Reassign tickets between agents',
      generate_report: 'Generate analytics report',
      view_statistics: 'View performance statistics',
      view_trends: 'View trend analysis',
      export_data: 'Export data to file',
      check_health: 'Check system health',
      view_alerts: 'View active alerts',
      acknowledge_alert: 'Acknowledge an alert',
      configure_settings: 'Configure system settings',
      search_knowledge: 'Search knowledge base',
      create_article: 'Create knowledge article',
      update_article: 'Update knowledge article',
      suggest_response: 'Get response suggestions',
      send_message: 'Send message to customer',
      schedule_followup: 'Schedule follow-up',
      create_note: 'Add internal note',
      create_rule: 'Create automation rule',
      update_rule: 'Update automation rule',
      view_automations: 'View automation rules',
      get_help: 'Get help',
      list_commands: 'List available commands',
      explain_feature: 'Explain a feature',
    };
    return descriptions[intent] || 'Unknown intent';
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Normalize text for processing
   */
  private normalizeText(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  /**
   * Calculate scores for all intents
   */
  private calculateScores(
    text: string,
    context?: CommandContext
  ): Array<{
    intent: IntentAction;
    category: IntentCategory;
    score: number;
    confidence: number;
  }> {
    const scores: Array<{
      intent: IntentAction;
      category: IntentCategory;
      score: number;
      confidence: number;
    }> = [];

    for (const pattern of this.patterns) {
      let score = 0;

      // Pattern matching (higher weight)
      for (const p of pattern.patterns) {
        const regex = new RegExp(`\\b${p}\\b`, 'i');
        if (regex.test(text)) {
          score += 3.0 * pattern.weight;
        }
      }

      // Keyword matching
      for (const keyword of pattern.keywords) {
        if (text.includes(keyword)) {
          score += 1.0 * pattern.weight;
        }
      }

      // Context boosts
      if (context) {
        score += this.getContextBoost(pattern, context);
      }

      // Check history for context
      if (context?.session_id) {
        const history = this.contextHistory.get(context.session_id) || [];
        if (history.length > 0) {
          const lastIntent = history[history.length - 1];
          // Boost related intents
          if (this.areRelatedIntents(lastIntent.intent, pattern.intent)) {
            score += 0.5;
          }
        }
      }

      if (score > 0) {
        scores.push({
          intent: pattern.intent,
          category: pattern.category,
          score,
          confidence: Math.min(score / 5, 1),
        });
      }
    }

    return scores;
  }

  /**
   * Get context-based boost
   */
  private getContextBoost(pattern: IntentPattern, context: CommandContext): number {
    let boost = 0;

    for (const [key, value] of Object.entries(pattern.context_boosts)) {
      const contextValue = (context as Record<string, unknown>)[key];

      if (typeof contextValue === 'string' && typeof value === 'object') {
        const boostMap = value as Record<string, number>;
        if (boostMap[contextValue]) {
          boost += boostMap[contextValue];
        }
      } else if (contextValue && typeof value === 'number') {
        boost += value;
      }
    }

    return boost;
  }

  /**
   * Check if two intents are related
   */
  private areRelatedIntents(intent1: IntentAction, intent2: IntentAction): boolean {
    const relatedGroups: IntentAction[][] = [
      ['view_ticket', 'update_ticket', 'close_ticket', 'assign_ticket', 'escalate_ticket'],
      ['view_customer', 'view_customer_history', 'search_customer'],
      ['search_tickets', 'view_ticket', 'prioritize_ticket'],
      ['generate_report', 'view_statistics', 'export_data'],
      ['search_knowledge', 'suggest_response'],
    ];

    for (const group of relatedGroups) {
      if (group.includes(intent1) && group.includes(intent2)) {
        return true;
      }
    }
    return false;
  }

  /**
   * Sort intents by score
   */
  private sortByScore(
    scores: Array<{ intent: IntentAction; category: IntentCategory; score: number; confidence: number }>
  ): Array<{ intent: IntentAction; category: IntentCategory; score: number; confidence: number }> {
    return scores.sort((a, b) => b.score - a.score);
  }

  /**
   * Calculate confidence from score
   */
  private calculateConfidence(
    topScore: number,
    allScores: Array<{ score: number }>
  ): number {
    if (allScores.length === 0) return 0;

    const secondScore = allScores.length > 1 ? allScores[1].score : 0;
    const margin = topScore - secondScore;

    // Higher margin = higher confidence
    const baseConfidence = Math.min(topScore / 5, 1);
    const marginBonus = Math.min(margin / 2, 0.3);

    return Math.min(baseConfidence + marginBonus, 1);
  }

  /**
   * Get confidence level from confidence score
   */
  private getConfidenceLevel(confidence: number): ConfidenceLevel {
    if (confidence >= 0.75) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
  }

  /**
   * Create unknown intent result
   */
  private createUnknownResult(text: string): IntentResult {
    return {
      intent: 'get_help',
      category: 'unknown',
      confidence: 0,
      confidence_level: 'low',
      raw_text: text,
      normalized_text: this.normalizeText(text),
    };
  }

  /**
   * Add result to history
   */
  private addToHistory(sessionId: string, result: IntentResult): void {
    if (!this.contextHistory.has(sessionId)) {
      this.contextHistory.set(sessionId, []);
    }

    const history = this.contextHistory.get(sessionId)!;
    history.push(result);

    // Keep last 10 intents
    if (history.length > 10) {
      history.shift();
    }
  }

  /**
   * Clear history for session
   */
  clearHistory(sessionId: string): void {
    this.contextHistory.delete(sessionId);
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createIntentClassifier(): IntentClassifier {
  return new IntentClassifier();
}

// ── Export intent patterns for reference ──────────────────────────────

export { INTENT_PATTERNS };
