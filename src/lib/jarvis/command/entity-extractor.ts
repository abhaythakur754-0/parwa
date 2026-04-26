/**
 * JARVIS Entity Extractor (Week 3 - Phase 1)
 *
 * Extracts entities (ticket IDs, customer names, dates, etc.) from text.
 * Uses pattern matching and NLP-like techniques for entity recognition.
 */

import type {
  EntityType,
  EntityResult,
  ExtractionResult,
  IntentAction,
} from '@/types/command';

// ── Entity Pattern Definitions ────────────────────────────────────────

interface EntityPattern {
  type: EntityType;
  patterns: RegExp[];
  normalization: (value: string) => string | number | Date;
  validation?: (value: string) => boolean;
  priority: number;
}

const ENTITY_PATTERNS: EntityPattern[] = [
  // Ticket ID - formats: TKT-123, #123, ticket 123, T123
  {
    type: 'ticket_id',
    patterns: [
      /\b(?:TKT|T)-?\d+\b/gi,
      /#(\d+)\b/g,
      /\bticket\s*#?\s*(\d+)\b/gi,
    ],
    normalization: (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, ''),
    priority: 10,
  },

  // Customer ID - formats: CUST-123, C123
  {
    type: 'customer_id',
    patterns: [
      /\b(?:CUST|C)-?\d+\b/gi,
      /\bcustomer\s*#?\s*(\d+)\b/gi,
    ],
    normalization: (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, ''),
    priority: 9,
  },

  // Agent ID - formats: AGT-123, A123
  {
    type: 'agent_id',
    patterns: [
      /\b(?:AGT|A)-?\d+\b/gi,
      /\bagent\s*#?\s*(\d+)\b/gi,
    ],
    normalization: (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, ''),
    priority: 9,
  },

  // Team ID
  {
    type: 'team_id',
    patterns: [
      /\b(?:TEAM|TM)-?\d+\b/gi,
      /\bteam\s*#?\s*(\d+)\b/gi,
    ],
    normalization: (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, ''),
    priority: 8,
  },

  // Email
  {
    type: 'email',
    patterns: [
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
    ],
    normalization: (v) => v.toLowerCase(),
    validation: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
    priority: 10,
  },

  // Phone
  {
    type: 'phone',
    patterns: [
      /\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b/g,
      /\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
    ],
    normalization: (v) => v.replace(/[^0-9]/g, ''),
    priority: 9,
  },

  // URL
  {
    type: 'url',
    patterns: [
      /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/g,
      /www\.[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/g,
    ],
    normalization: (v) => v.startsWith('http') ? v : `https://${v}`,
    priority: 8,
  },

  // Priority
  {
    type: 'priority',
    patterns: [
      /\b(urgent|critical|emergency)\b/gi,
      /\bhigh\s*(?:priority)?\b/gi,
      /\bmedium\s*(?:priority)?\b/gi,
      /\bnormal\s*(?:priority)?\b/gi,
      /\blow\s*(?:priority)?\b/gi,
    ],
    normalization: (v) => {
      const lower = v.toLowerCase();
      if (/urgent|critical|emergency/.test(lower)) return 'urgent';
      if (/high/.test(lower)) return 'high';
      if (/medium/.test(lower)) return 'medium';
      if (/normal/.test(lower)) return 'normal';
      if (/low/.test(lower)) return 'low';
      return lower;
    },
    priority: 7,
  },

  // Status
  {
    type: 'status',
    patterns: [
      /\b(open|opened|new|pending)\b/gi,
      /\b(in[-\s]?progress|active|working)\b/gi,
      /\b(resolved|closed|complete|done|fixed)\b/gi,
      /\b(on[-\s]?hold|waiting|suspended)\b/gi,
      /\b(escalated|escalation)\b/gi,
    ],
    normalization: (v) => {
      const lower = v.toLowerCase().replace(/[-\s]/g, '_');
      if (/open|new|pending/.test(lower)) return 'open';
      if (/progress|active|working/.test(lower)) return 'in_progress';
      if (/resolved|closed|complete|done|fixed/.test(lower)) return 'resolved';
      if (/hold|waiting|suspended/.test(lower)) return 'on_hold';
      if (/escalated/.test(lower)) return 'escalated';
      return lower;
    },
    priority: 7,
  },

  // Channel
  {
    type: 'channel',
    patterns: [
      /\b(email|mail|e-mail)\b/gi,
      /\b(chat|live\s*chat|webchat)\b/gi,
      /\b(phone|call|voice)\b/gi,
      /\b(sms|text|message)\b/gi,
      /\b(whatsapp|wa)\b/gi,
      /\b(social|twitter|facebook|instagram)\b/gi,
    ],
    normalization: (v) => {
      const lower = v.toLowerCase();
      if (/mail|e-mail/.test(lower)) return 'email';
      if (/chat/.test(lower)) return 'chat';
      if (/phone|call|voice/.test(lower)) return 'phone';
      if (/sms|text/.test(lower)) return 'sms';
      if (/whatsapp|wa/.test(lower)) return 'whatsapp';
      if (/social|twitter|facebook|instagram/.test(lower)) return 'social';
      return lower;
    },
    priority: 6,
  },

  // Category
  {
    type: 'category',
    patterns: [
      /\bcategory[:\s]+([a-zA-Z\s]+)/gi,
      /\b(?:categorized as|in category)\s+([a-zA-Z\s]+)/gi,
    ],
    normalization: (v) => v.toLowerCase().trim(),
    priority: 5,
  },

  // Tag
  {
    type: 'tag',
    patterns: [
      /#([a-zA-Z0-9_-]+)/g,
      /\btag[:\s]+([a-zA-Z0-9_-]+)/gi,
      /\btagged\s+(?:as\s+)?([a-zA-Z0-9_-]+)/gi,
    ],
    normalization: (v) => v.toLowerCase().replace(/[^a-z0-9_-]/g, ''),
    priority: 5,
  },

  // Date
  {
    type: 'date',
    patterns: [
      /\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b/g,
      /\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b/g,
      /\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b/gi,
      /\b(today|tomorrow|yesterday)\b/gi,
      /\b(next|this|last)\s+(week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/gi,
    ],
    normalization: (v) => {
      const lower = v.toLowerCase();
      const now = new Date();

      if (lower === 'today') return now.toISOString().split('T')[0];
      if (lower === 'tomorrow') {
        const tomorrow = new Date(now.getTime() + 86400000);
        return tomorrow.toISOString().split('T')[0];
      }
      if (lower === 'yesterday') {
        const yesterday = new Date(now.getTime() - 86400000);
        return yesterday.toISOString().split('T')[0];
      }

      // Try to parse the date
      try {
        const parsed = new Date(v);
        if (!isNaN(parsed.getTime())) {
          return parsed.toISOString().split('T')[0];
        }
      } catch {
        // Return original if parsing fails
      }
      return v;
    },
    priority: 8,
  },

  // Time
  {
    type: 'time',
    patterns: [
      /\b(\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)\b/gi,
      /\b(\d{1,2}\s*(?:am|pm))\b/gi,
      /\b(midnight|noon|morning|afternoon|evening)\b/gi,
    ],
    normalization: (v) => v.toLowerCase(),
    priority: 7,
  },

  // Duration
  {
    type: 'duration',
    patterns: [
      /\b(\d+)\s*(?:hours?|hrs?|h)\b/gi,
      /\b(\d+)\s*(?:minutes?|mins?|m)\b/gi,
      /\b(\d+)\s*(?:days?|d)\b/gi,
      /\b(\d+)\s*(?:weeks?|w)\b/gi,
    ],
    normalization: (v) => v.toLowerCase(),
    priority: 6,
  },

  // Number
  {
    type: 'number',
    patterns: [
      /\b\d+\b/g,
      /\b(one|two|three|four|five|six|seven|eight|nine|ten)\b/gi,
      /\b(hundred|thousand|million)\b/gi,
    ],
    normalization: (v) => {
      const wordToNum: Record<string, number> = {
        one: 1, two: 2, three: 3, four: 4, five: 5,
        six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
        hundred: 100, thousand: 1000, million: 1000000,
      };
      const lower = v.toLowerCase();
      return wordToNum[lower] ?? parseInt(v, 10);
    },
    priority: 4,
  },

  // Limit
  {
    type: 'limit',
    patterns: [
      /\blimit[:\s]+(\d+)\b/gi,
      /\btop\s+(\d+)\b/gi,
      /\bfirst\s+(\d+)\b/gi,
      /\bshow\s+(\d+)\b/gi,
    ],
    normalization: (v) => parseInt(v, 10),
    priority: 5,
  },

  // Sort Order
  {
    type: 'sort_order',
    patterns: [
      /\b(asc(?:ending)?|desc(?:ending)?)\b/gi,
      /\b(sort|order)\s+(by\s+)?(newest|oldest|latest|recent|first|last)\b/gi,
      /\b(newest|oldest|latest|recent)\s+(first|last)?\b/gi,
    ],
    normalization: (v) => {
      const lower = v.toLowerCase();
      if (/desc|oldest|last/.test(lower)) return 'desc';
      return 'asc';
    },
    priority: 5,
  },
];

// ── Intent-specific entity expectations ───────────────────────────────

const INTENT_ENTITY_EXPECTATIONS: Partial<Record<IntentAction, EntityType[]>> = {
  view_ticket: ['ticket_id'],
  update_ticket: ['ticket_id'],
  close_ticket: ['ticket_id'],
  assign_ticket: ['ticket_id', 'agent_id'],
  escalate_ticket: ['ticket_id'],
  prioritize_ticket: ['ticket_id', 'priority'],
  tag_ticket: ['ticket_id', 'tag'],
  merge_tickets: ['ticket_id'],
  search_tickets: ['status', 'priority', 'tag', 'date', 'channel', 'limit'],
  view_customer: ['customer_id', 'email'],
  search_customer: ['email', 'phone', 'keyword'],
  view_customer_history: ['customer_id'],
  assign_to_agent: ['agent_id', 'ticket_id'],
  generate_report: ['date', 'duration'],
  view_statistics: ['date', 'channel'],
  export_data: ['date', 'status', 'limit'],
  send_message: ['customer_id', 'ticket_id'],
  schedule_followup: ['date', 'time', 'duration'],
  acknowledge_alert: ['ticket_id'],
  search_knowledge: ['keyword'],
};

// ── Entity Extractor Class ────────────────────────────────────────────

export class EntityExtractor {
  private patterns: EntityPattern[];

  constructor() {
    this.patterns = ENTITY_PATTERNS.sort((a, b) => b.priority - a.priority);
  }

  /**
   * Extract entities from text
   */
  extract(text: string, intent?: IntentAction): ExtractionResult {
    const startTime = Date.now();
    const entities: EntityResult[] = [];
    const usedPositions = new Set<number>();

    for (const pattern of this.patterns) {
      // Skip if intent doesn't expect this entity type
      if (intent && !this.isExpectedEntity(pattern.type, intent)) {
        continue;
      }

      for (const regex of pattern.patterns) {
        let match;
        const globalRegex = new RegExp(regex.source, regex.flags);

        while ((match = globalRegex.exec(text)) !== null) {
          const startIndex = match.index;
          const endIndex = startIndex + match[0].length;

          // Check for overlapping matches
          let overlaps = false;
          for (let i = startIndex; i < endIndex; i++) {
            if (usedPositions.has(i)) {
              overlaps = true;
              break;
            }
          }

          if (overlaps) continue;

          // Mark positions as used
          for (let i = startIndex; i < endIndex; i++) {
            usedPositions.add(i);
          }

          const rawValue = match[1] || match[0];
          const normalizedValue = pattern.normalization(rawValue);

          // Validate if needed
          if (pattern.validation && !pattern.validation(rawValue)) {
            continue;
          }

          entities.push({
            type: pattern.type,
            value: rawValue,
            normalized_value: normalizedValue,
            start_index: startIndex,
            end_index: endIndex,
            confidence: this.calculateConfidence(pattern.type, match[0]),
            source: 'extracted',
          });
        }
      }
    }

    // Add inferred entities based on intent
    if (intent) {
      const inferred = this.inferEntities(text, intent, entities);
      entities.push(...inferred);
    }

    // Sort by position
    entities.sort((a, b) => a.start_index - b.start_index);

    return {
      entities,
      raw_text: text,
      extraction_time_ms: Date.now() - startTime,
    };
  }

  /**
   * Extract specific entity type
   */
  extractType(text: string, type: EntityType): EntityResult[] {
    const result = this.extract(text);
    return result.entities.filter((e) => e.type === type);
  }

  /**
   * Get first entity of a type
   */
  getFirstEntity(entities: EntityResult[], type: EntityType): EntityResult | undefined {
    return entities.find((e) => e.type === type);
  }

  /**
   * Get all entities of a type
   */
  getEntitiesByType(entities: EntityResult[], type: EntityType): EntityResult[] {
    return entities.filter((e) => e.type === type);
  }

  /**
   * Convert entities to params object
   */
  entitiesToParams(entities: EntityResult[]): Record<string, unknown> {
    const params: Record<string, unknown> = {};

    for (const entity of entities) {
      const key = entity.type;
      const value = entity.normalized_value ?? entity.value;

      // Handle multiple values for same type
      if (params[key] !== undefined) {
        if (!Array.isArray(params[key])) {
          params[key] = [params[key]];
        }
        (params[key] as unknown[]).push(value);
      } else {
        params[key] = value;
      }
    }

    return params;
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Check if entity type is expected for intent
   */
  private isExpectedEntity(type: EntityType, intent: IntentAction): boolean {
    const expected = INTENT_ENTITY_EXPECTATIONS[intent];
    if (!expected) return true; // Allow all if no expectations defined
    return expected.includes(type);
  }

  /**
   * Calculate confidence for entity match
   */
  private calculateConfidence(type: EntityType, matchedText: string): number {
    // Base confidence by type
    const baseConfidence: Partial<Record<EntityType, number>> = {
      ticket_id: 0.95,
      customer_id: 0.95,
      agent_id: 0.95,
      email: 0.95,
      phone: 0.9,
      url: 0.9,
      date: 0.85,
      time: 0.85,
      priority: 0.9,
      status: 0.85,
      channel: 0.85,
      number: 0.8,
      tag: 0.8,
      keyword: 0.7,
    };

    const base = baseConfidence[type] ?? 0.75;

    // Adjust based on match quality
    const length = matchedText.length;
    if (length <= 2) return base * 0.9;
    if (length <= 5) return base * 0.95;
    return base;
  }

  /**
   * Infer entities based on intent and context
   */
  private inferEntities(
    text: string,
    intent: IntentAction,
    existingEntities: EntityResult[]
  ): EntityResult[] {
    const inferred: EntityResult[] = [];

    // Infer priority from words
    if (
      ['prioritize_ticket', 'create_ticket', 'update_ticket'].includes(intent) &&
      !existingEntities.find((e) => e.type === 'priority')
    ) {
      const urgentMatch = /\b(right\s*now|immediately|asap|urgently|quickly)\b/i.exec(text);
      if (urgentMatch) {
        inferred.push({
          type: 'priority',
          value: urgentMatch[0],
          normalized_value: 'urgent',
          start_index: urgentMatch.index,
          end_index: urgentMatch.index + urgentMatch[0].length,
          confidence: 0.8,
          source: 'inferred',
        });
      }
    }

    // Infer status from words
    if (
      ['search_tickets', 'view_ticket'].includes(intent) &&
      !existingEntities.find((e) => e.type === 'status')
    ) {
      const openMatch = /\b(my\s+)?(open|pending|active)\s+(tickets|issues)\b/i.exec(text);
      if (openMatch) {
        inferred.push({
          type: 'status',
          value: openMatch[0],
          normalized_value: 'open',
          start_index: openMatch.index,
          end_index: openMatch.index + openMatch[0].length,
          confidence: 0.8,
          source: 'inferred',
        });
      }
    }

    return inferred;
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createEntityExtractor(): EntityExtractor {
  return new EntityExtractor();
}

// ── Export patterns for reference ─────────────────────────────────────

export { ENTITY_PATTERNS, INTENT_ENTITY_EXPECTATIONS };
