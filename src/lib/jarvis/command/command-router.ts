/**
 * JARVIS Command Router (Week 3 - Phase 1)
 *
 * Routes commands to appropriate handlers based on intent.
 * Handles validation, permission checking, and variant availability.
 */

import type {
  IntentAction,
  IntentCategory,
  CommandAction,
  RouteDefinition,
  CommandContext,
  ValidationRule,
  ExecutionMode,
} from '@/types/command';

// ── Route Definitions ─────────────────────────────────────────────────

const ROUTE_DEFINITIONS: RouteDefinition[] = [
  // Ticket Routes
  {
    intent: 'create_ticket',
    handler: 'ticket_handler.create',
    params_schema: {
      required: [
        { name: 'subject', type: 'string', description: 'Ticket subject/title' },
      ],
      optional: [
        { name: 'description', type: 'string', description: 'Ticket description' },
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
        { name: 'priority', type: 'string', description: 'Priority level', enum: ['low', 'medium', 'high', 'urgent'] },
        { name: 'category', type: 'string', description: 'Ticket category' },
        { name: 'channel', type: 'string', description: 'Source channel' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.create'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'view_ticket',
    handler: 'ticket_handler.view',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID to view' },
      ],
      optional: [],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'update_ticket',
    handler: 'ticket_handler.update',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID to update' },
      ],
      optional: [
        { name: 'subject', type: 'string', description: 'New subject' },
        { name: 'description', type: 'string', description: 'New description' },
        { name: 'status', type: 'string', description: 'New status' },
        { name: 'priority', type: 'string', description: 'New priority' },
        { name: 'category', type: 'string', description: 'New category' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'close_ticket',
    handler: 'ticket_handler.close',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID to close' },
      ],
      optional: [
        { name: 'resolution', type: 'string', description: 'Resolution notes' },
        { name: 'resolution_type', type: 'string', description: 'How it was resolved' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.close'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'assign_ticket',
    handler: 'ticket_handler.assign',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID to assign' },
        { name: 'agent_id', type: 'string', description: 'Agent ID to assign to' },
      ],
      optional: [
        { name: 'reason', type: 'string', description: 'Reason for assignment' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.assign'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'escalate_ticket',
    handler: 'ticket_handler.escalate',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID to escalate' },
      ],
      optional: [
        { name: 'reason', type: 'string', description: 'Escalation reason' },
        { name: 'escalate_to', type: 'string', description: 'Team or agent to escalate to' },
      ],
    },
    risk_level: 'medium',
    execution_mode: 'draft',
    required_permissions: ['ticket.escalate'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'merge_tickets',
    handler: 'ticket_handler.merge',
    params_schema: {
      required: [
        { name: 'ticket_ids', type: 'array', description: 'Array of ticket IDs to merge' },
        { name: 'primary_ticket_id', type: 'string', description: 'Primary ticket to merge into' },
      ],
      optional: [],
    },
    risk_level: 'medium',
    execution_mode: 'draft',
    required_permissions: ['ticket.merge'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'search_tickets',
    handler: 'ticket_handler.search',
    params_schema: {
      required: [],
      optional: [
        { name: 'status', type: 'string', description: 'Filter by status' },
        { name: 'priority', type: 'string', description: 'Filter by priority' },
        { name: 'category', type: 'string', description: 'Filter by category' },
        { name: 'customer_id', type: 'string', description: 'Filter by customer' },
        { name: 'agent_id', type: 'string', description: 'Filter by agent' },
        { name: 'tag', type: 'string', description: 'Filter by tag' },
        { name: 'date_from', type: 'date', description: 'From date' },
        { name: 'date_to', type: 'date', description: 'To date' },
        { name: 'keyword', type: 'string', description: 'Search keyword' },
        { name: 'limit', type: 'number', description: 'Max results', default: 20 },
        { name: 'sort', type: 'string', description: 'Sort order' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'prioritize_ticket',
    handler: 'ticket_handler.prioritize',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID' },
        { name: 'priority', type: 'string', description: 'New priority', enum: ['low', 'medium', 'high', 'urgent'] },
      ],
      optional: [],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'tag_ticket',
    handler: 'ticket_handler.tag',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID' },
        { name: 'tag', type: 'string', description: 'Tag to add/remove' },
      ],
      optional: [
        { name: 'action', type: 'string', description: 'add or remove', default: 'add' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },

  // Customer Routes
  {
    intent: 'view_customer',
    handler: 'customer_handler.view',
    params_schema: {
      required: [],
      optional: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
        { name: 'email', type: 'string', description: 'Customer email' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['customer.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'search_customer',
    handler: 'customer_handler.search',
    params_schema: {
      required: [],
      optional: [
        { name: 'email', type: 'string', description: 'Search by email' },
        { name: 'phone', type: 'string', description: 'Search by phone' },
        { name: 'name', type: 'string', description: 'Search by name' },
        { name: 'keyword', type: 'string', description: 'General keyword search' },
        { name: 'limit', type: 'number', description: 'Max results', default: 10 },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['customer.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'view_customer_history',
    handler: 'customer_handler.history',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
      ],
      optional: [
        { name: 'limit', type: 'number', description: 'Max results', default: 20 },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['customer.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },

  // Agent Routes
  {
    intent: 'view_agent_status',
    handler: 'agent_handler.status',
    params_schema: {
      required: [],
      optional: [
        { name: 'agent_id', type: 'string', description: 'Specific agent ID' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['agent.view'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'view_workload',
    handler: 'agent_handler.workload',
    params_schema: {
      required: [],
      optional: [
        { name: 'team_id', type: 'string', description: 'Filter by team' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['agent.view'],
    variant_availability: ['parwa', 'parwa_high'],
  },

  // Analytics Routes
  {
    intent: 'generate_report',
    handler: 'analytics_handler.report',
    params_schema: {
      required: [
        { name: 'report_type', type: 'string', description: 'Type of report' },
      ],
      optional: [
        { name: 'date_from', type: 'date', description: 'From date' },
        { name: 'date_to', type: 'date', description: 'To date' },
        { name: 'format', type: 'string', description: 'Output format', default: 'json' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['analytics.view'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'view_statistics',
    handler: 'analytics_handler.statistics',
    params_schema: {
      required: [],
      optional: [
        { name: 'period', type: 'string', description: 'Time period', default: 'today' },
        { name: 'metrics', type: 'array', description: 'Specific metrics to show' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['analytics.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'export_data',
    handler: 'analytics_handler.export',
    params_schema: {
      required: [
        { name: 'data_type', type: 'string', description: 'Type of data to export' },
      ],
      optional: [
        { name: 'format', type: 'string', description: 'Export format', default: 'csv' },
        { name: 'date_from', type: 'date', description: 'From date' },
        { name: 'date_to', type: 'date', description: 'To date' },
      ],
    },
    risk_level: 'medium',
    execution_mode: 'draft',
    required_permissions: ['analytics.export'],
    variant_availability: ['parwa', 'parwa_high'],
  },

  // System Routes
  {
    intent: 'check_health',
    handler: 'system_handler.health',
    params_schema: {
      required: [],
      optional: [],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: [],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'view_alerts',
    handler: 'system_handler.alerts',
    params_schema: {
      required: [],
      optional: [
        { name: 'status', type: 'string', description: 'Filter by alert status' },
        { name: 'severity', type: 'string', description: 'Filter by severity' },
        { name: 'limit', type: 'number', description: 'Max results', default: 20 },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['alerts.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'acknowledge_alert',
    handler: 'system_handler.acknowledge_alert',
    params_schema: {
      required: [
        { name: 'alert_id', type: 'string', description: 'Alert ID to acknowledge' },
      ],
      optional: [
        { name: 'notes', type: 'string', description: 'Acknowledgement notes' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['alerts.manage'],
    variant_availability: ['parwa', 'parwa_high'],
  },

  // Knowledge Routes
  {
    intent: 'search_knowledge',
    handler: 'knowledge_handler.search',
    params_schema: {
      required: [
        { name: 'keyword', type: 'string', description: 'Search keyword' },
      ],
      optional: [
        { name: 'category', type: 'string', description: 'Filter by category' },
        { name: 'limit', type: 'number', description: 'Max results', default: 10 },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['knowledge.view'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'suggest_response',
    handler: 'knowledge_handler.suggest',
    params_schema: {
      required: [],
      optional: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID for context' },
        { name: 'customer_id', type: 'string', description: 'Customer ID for context' },
        { name: 'tone', type: 'string', description: 'Response tone' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['knowledge.view'],
    variant_availability: ['parwa', 'parwa_high'],
  },

  // Communication Routes
  {
    intent: 'send_message',
    handler: 'communication_handler.send',
    params_schema: {
      required: [
        { name: 'message', type: 'string', description: 'Message content' },
      ],
      optional: [
        { name: 'ticket_id', type: 'string', description: 'Related ticket' },
        { name: 'customer_id', type: 'string', description: 'Target customer' },
        { name: 'channel', type: 'string', description: 'Send via channel' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['communication.send'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'schedule_followup',
    handler: 'communication_handler.schedule_followup',
    params_schema: {
      required: [
        { name: 'date', type: 'date', description: 'Follow-up date' },
      ],
      optional: [
        { name: 'time', type: 'string', description: 'Follow-up time' },
        { name: 'ticket_id', type: 'string', description: 'Related ticket' },
        { name: 'customer_id', type: 'string', description: 'Customer to follow up' },
        { name: 'note', type: 'string', description: 'Follow-up note' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['communication.schedule'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'create_note',
    handler: 'communication_handler.create_note',
    params_schema: {
      required: [
        { name: 'content', type: 'string', description: 'Note content' },
      ],
      optional: [
        { name: 'ticket_id', type: 'string', description: 'Related ticket' },
        { name: 'customer_id', type: 'string', description: 'Related customer' },
        { name: 'visibility', type: 'string', description: 'Note visibility', default: 'internal' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: ['notes.create'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },

  // Help Routes
  {
    intent: 'get_help',
    handler: 'help_handler.get_help',
    params_schema: {
      required: [],
      optional: [
        { name: 'topic', type: 'string', description: 'Help topic' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: [],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'list_commands',
    handler: 'help_handler.list_commands',
    params_schema: {
      required: [],
      optional: [
        { name: 'category', type: 'string', description: 'Filter by category' },
      ],
    },
    risk_level: 'low',
    execution_mode: 'direct',
    required_permissions: [],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },

  // ── CRITICAL: Financial & Account Routes (ALWAYS require approval) ──
  // Per PARWA documentation, these actions ALWAYS require human approval:
  // - All refunds (any type, any amount)
  // - All returns (any item)
  // - Account changes (billing, security, email, password)
  // - VIP customer actions
  // - Policy exceptions
  // - Financial transactions (credits, adjustments, discounts >$10)

  {
    intent: 'refund_request',
    handler: 'refund_handler.process',
    params_schema: {
      required: [
        { name: 'order_id', type: 'string', description: 'Order ID to refund' },
      ],
      optional: [
        { name: 'amount', type: 'number', description: 'Refund amount' },
        { name: 'reason', type: 'string', description: 'Reason for refund' },
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
        { name: 'customer_tier', type: 'string', description: 'Customer tier (standard, premium, vip)' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'return_request',
    handler: 'return_handler.process',
    params_schema: {
      required: [
        { name: 'order_id', type: 'string', description: 'Order ID for return' },
      ],
      optional: [
        { name: 'item_id', type: 'string', description: 'Specific item ID' },
        { name: 'reason', type: 'string', description: 'Reason for return' },
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'email_change',
    handler: 'account_handler.update_email',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
      ],
      optional: [
        { name: 'old_email', type: 'string', description: 'Current email' },
        { name: 'new_email', type: 'string', description: 'New email' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'password_change',
    handler: 'account_handler.update_password',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
      ],
      optional: [],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'billing_change',
    handler: 'account_handler.update_billing',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
      ],
      optional: [
        { name: 'new_address', type: 'string', description: 'New billing address' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['mini_parwa', 'parwa', 'parwa_high'],
  },
  {
    intent: 'vip_action',
    handler: 'vip_handler.special_action',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'VIP Customer ID' },
        { name: 'action_type', type: 'string', description: 'Type of action' },
      ],
      optional: [
        { name: 'discount_percent', type: 'number', description: 'Discount percentage' },
        { name: 'credit_amount', type: 'number', description: 'Credit amount' },
        { name: 'notes', type: 'string', description: 'Action notes' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'policy_exception',
    handler: 'policy_handler.exception',
    params_schema: {
      required: [
        { name: 'ticket_id', type: 'string', description: 'Ticket ID' },
        { name: 'exception_reason', type: 'string', description: 'Reason for exception' },
      ],
      optional: [
        { name: 'policy_rule', type: 'string', description: 'Policy rule being excepted' },
        { name: 'requested_action', type: 'string', description: 'Requested action' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['parwa', 'parwa_high'],
  },
  {
    intent: 'financial_transaction',
    handler: 'financial_handler.adjustment',
    params_schema: {
      required: [
        { name: 'customer_id', type: 'string', description: 'Customer ID' },
        { name: 'amount', type: 'number', description: 'Transaction amount' },
        { name: 'transaction_type', type: 'string', description: 'Type: credit, adjustment, discount' },
      ],
      optional: [
        { name: 'reason', type: 'string', description: 'Transaction reason' },
        { name: 'ticket_id', type: 'string', description: 'Related ticket' },
      ],
    },
    risk_level: 'high',
    execution_mode: 'draft', // ALWAYS requires approval
    required_permissions: ['ticket.update'],
    variant_availability: ['parwa', 'parwa_high'],
  },
];

// ── Command Router Class ──────────────────────────────────────────────

export class CommandRouter {
  private routes: Map<IntentAction, RouteDefinition>;

  constructor() {
    this.routes = new Map(ROUTE_DEFINITIONS.map((r) => [r.intent, r]));
  }

  /**
   * Route intent to action
   */
  route(
    intent: IntentAction,
    params: Record<string, unknown>,
    context: CommandContext
  ): CommandAction {
    const route = this.routes.get(intent);

    if (!route) {
      return this.createUnknownAction(intent);
    }

    // Check variant availability
    if (!route.variant_availability.includes(context.variant)) {
      return this.createUnavailableAction(intent, context.variant);
    }

    // Check permissions
    const permissionCheck = this.checkPermissions(route, context);
    if (!permissionCheck.allowed) {
      return this.createPermissionDeniedAction(intent, permissionCheck.missing!);
    }

    // Validate params
    const validation = this.validateParams(route, params);
    if (!validation.valid) {
      return this.createInvalidParamsAction(intent, validation.errors!);
    }

    // Determine execution mode
    const executionMode = this.determineExecutionMode(route, params, context);

    return {
      type: intent,
      category: this.getCategoryFromIntent(intent),
      handler: route.handler,
      params: this.applyDefaults(route, params),
      required_params: route.params_schema.required.map((p) => p.name),
      optional_params: route.params_schema.optional.map((p) => p.name),
      risk_level: route.risk_level,
      reversible: this.isReversible(route),
      timeout_ms: this.getTimeout(route),
    };
  }

  /**
   * Get route definition
   */
  getRoute(intent: IntentAction): RouteDefinition | undefined {
    return this.routes.get(intent);
  }

  /**
   * Get all routes
   */
  getAllRoutes(): RouteDefinition[] {
    return Array.from(this.routes.values());
  }

  /**
   * Get routes by category
   */
  getRoutesByCategory(category: IntentCategory): RouteDefinition[] {
    return this.getAllRoutes().filter((r) =>
      this.getCategoryFromIntent(r.intent) === category
    );
  }

  /**
   * Get available intents for variant
   */
  getAvailableIntents(variant: 'mini_parwa' | 'parwa' | 'parwa_high'): IntentAction[] {
    return this.getAllRoutes()
      .filter((r) => r.variant_availability.includes(variant))
      .map((r) => r.intent);
  }

  /**
   * Check if intent is available for variant
   */
  isIntentAvailable(intent: IntentAction, variant: 'mini_parwa' | 'parwa' | 'parwa_high'): boolean {
    const route = this.routes.get(intent);
    return route ? route.variant_availability.includes(variant) : false;
  }

  /**
   * Add custom route
   */
  addRoute(route: RouteDefinition): void {
    this.routes.set(route.intent, route);
  }

  // ── Private Methods ────────────────────────────────────────────────

  /**
   * Check permissions
   */
  private checkPermissions(
    route: RouteDefinition,
    context: CommandContext
  ): { allowed: boolean; missing?: string[] } {
    if (route.required_permissions.length === 0) {
      return { allowed: true };
    }

    const missing = route.required_permissions.filter(
      (p) => !context.permissions.includes(p)
    );

    return {
      allowed: missing.length === 0,
      missing: missing.length > 0 ? missing : undefined,
    };
  }

  /**
   * Validate params against schema
   */
  private validateParams(
    route: RouteDefinition,
    params: Record<string, unknown>
  ): { valid: boolean; errors?: string[] } {
    const errors: string[] = [];

    // Check required params
    for (const required of route.params_schema.required) {
      if (params[required.name] === undefined) {
        errors.push(`Missing required parameter: ${required.name}`);
      }
    }

    // Validate types
    for (const [name, value] of Object.entries(params)) {
      const paramDef = [
        ...route.params_schema.required,
        ...route.params_schema.optional,
      ].find((p) => p.name === name);

      if (paramDef && value !== undefined) {
        const typeError = this.validateType(name, value, paramDef.type);
        if (typeError) errors.push(typeError);

        // Check enum values
        if (paramDef.enum && !paramDef.enum.includes(value as string)) {
          errors.push(`${name} must be one of: ${paramDef.enum.join(', ')}`);
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
    };
  }

  /**
   * Validate parameter type
   */
  private validateType(name: string, value: unknown, expectedType: string): string | null {
    const actualType = Array.isArray(value) ? 'array' : typeof value;

    if (expectedType === 'date') {
      if (!(value instanceof Date) && typeof value !== 'string') {
        return `${name} must be a date`;
      }
      return null;
    }

    if (actualType !== expectedType) {
      return `${name} must be of type ${expectedType}, got ${actualType}`;
    }

    return null;
  }

  /**
   * Apply default values
   */
  private applyDefaults(
    route: RouteDefinition,
    params: Record<string, unknown>
  ): Record<string, unknown> {
    const result = { ...params };

    for (const optional of route.params_schema.optional) {
      if (result[optional.name] === undefined && optional.default !== undefined) {
        result[optional.name] = optional.default;
      }
    }

    return result;
  }

  /**
   * Determine execution mode
   */
  private determineExecutionMode(
    route: RouteDefinition,
    params: Record<string, unknown>,
    context: CommandContext
  ): ExecutionMode {
    // If route specifies draft mode, use it
    if (route.execution_mode === 'draft') {
      return 'draft';
    }

    // Check risk level for variant
    const variantLimits = {
      mini_parwa: ['low'],
      parwa: ['low', 'medium'],
      parwa_high: ['low', 'medium', 'high'],
    };

    const allowedRisks = variantLimits[context.variant];
    if (!allowedRisks.includes(route.risk_level)) {
      return 'draft';
    }

    // Check if bulk operation
    if (route.risk_level === 'medium' || route.risk_level === 'high') {
      return 'draft';
    }

    return 'direct';
  }

  /**
   * Get category from intent
   */
  private getCategoryFromIntent(intent: IntentAction): IntentCategory {
    if (intent.startsWith('create_') || intent.startsWith('update_') || intent.startsWith('view_')) {
      const entity = intent.split('_')[1];
      if (['ticket', 'customer', 'agent', 'knowledge'].includes(entity)) {
        return entity as IntentCategory;
      }
    }

    if (intent.includes('report') || intent.includes('statistics') || intent.includes('export')) {
      return 'analytics';
    }

    if (intent.includes('health') || intent.includes('alert') || intent.includes('system')) {
      return 'system';
    }

    if (intent.includes('message') || intent.includes('followup') || intent.includes('note')) {
      return 'communication';
    }

    if (intent.includes('help') || intent.includes('command')) {
      return 'help';
    }

    return 'unknown';
  }

  /**
   * Check if action is reversible
   */
  private isReversible(route: RouteDefinition): boolean {
    return route.risk_level !== 'critical';
  }

  /**
   * Get timeout for route
   */
  private getTimeout(route: RouteDefinition): number {
    const timeouts: Record<string, number> = {
      low: 30000,
      medium: 60000,
      high: 120000,
      critical: 300000,
    };
    return timeouts[route.risk_level] || 30000;
  }

  /**
   * Create unknown action
   */
  private createUnknownAction(intent: IntentAction): CommandAction {
    return {
      type: intent,
      category: 'unknown',
      handler: 'unknown_handler',
      params: {},
      required_params: [],
      optional_params: [],
      risk_level: 'low',
      reversible: false,
      timeout_ms: 30000,
    };
  }

  /**
   * Create unavailable action
   */
  private createUnavailableAction(intent: IntentAction, variant: string): CommandAction {
    return {
      type: intent,
      category: 'unknown',
      handler: 'unavailable_handler',
      params: { variant },
      required_params: [],
      optional_params: [],
      risk_level: 'low',
      reversible: false,
      timeout_ms: 30000,
    };
  }

  /**
   * Create permission denied action
   */
  private createPermissionDeniedAction(intent: IntentAction, missing: string[]): CommandAction {
    return {
      type: intent,
      category: 'unknown',
      handler: 'permission_denied_handler',
      params: { missing_permissions: missing },
      required_params: [],
      optional_params: [],
      risk_level: 'low',
      reversible: false,
      timeout_ms: 30000,
    };
  }

  /**
   * Create invalid params action
   */
  private createInvalidParamsAction(intent: IntentAction, errors: string[]): CommandAction {
    return {
      type: intent,
      category: 'unknown',
      handler: 'invalid_params_handler',
      params: { validation_errors: errors },
      required_params: [],
      optional_params: [],
      risk_level: 'low',
      reversible: false,
      timeout_ms: 30000,
    };
  }
}

// ── Factory Function ─────────────────────────────────────────────────

export function createCommandRouter(): CommandRouter {
  return new CommandRouter();
}

// ── Export route definitions ──────────────────────────────────────────

export { ROUTE_DEFINITIONS };
