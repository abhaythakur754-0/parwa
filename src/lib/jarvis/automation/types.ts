/**
 * JARVIS Custom Automation Types - Week 11 (Phase 3)
 *
 * Type definitions for visual workflow editor, triggers, actions, and automation testing.
 */

import type { Variant } from '@/types/variant';

// ── Automation Configuration ──────────────────────────────────────────

export interface AutomationConfig {
  /** Tenant ID */
  tenant_id: string;
  /** Variant for capability gating */
  variant: Variant;
  /** Enable automation builder */
  automation_enabled: boolean;
  /** Maximum automations per tenant */
  max_automations: number;
  /** Enable visual editor */
  visual_editor_enabled: boolean;
  /** Enable testing framework */
  testing_enabled: boolean;
  /** Maximum workflow steps */
  max_workflow_steps: number;
  /** Execution timeout in seconds */
  execution_timeout_seconds: number;
}

export const DEFAULT_AUTOMATION_CONFIG: Record<Variant, Partial<AutomationConfig>> = {
  mini_parwa: {
    automation_enabled: false,
    visual_editor_enabled: false,
    testing_enabled: false,
    max_automations: 0,
    max_workflow_steps: 0,
  },
  parwa: {
    automation_enabled: true,
    visual_editor_enabled: true,
    testing_enabled: true,
    max_automations: 25,
    max_workflow_steps: 20,
  },
  parwa_high: {
    automation_enabled: true,
    visual_editor_enabled: true,
    testing_enabled: true,
    max_automations: 100,
    max_workflow_steps: 50,
  },
};

// ── Workflow Types ─────────────────────────────────────────────────────

export interface Workflow {
  /** Workflow ID */
  id: string;
  /** Tenant ID */
  tenant_id: string;
  /** Workflow name */
  name: string;
  /** Description */
  description?: string;
  /** Workflow status */
  status: WorkflowStatus;
  /** Trigger configuration */
  trigger: WorkflowTrigger;
  /** Workflow steps */
  steps: WorkflowStep[];
  /** Connections between steps */
  connections: WorkflowConnection[];
  /** Variables */
  variables: WorkflowVariable[];
  /** Created at */
  created_at: Date;
  /** Updated at */
  updated_at: Date;
  /** Created by */
  created_by: string;
  /** Last modified by */
  modified_by?: string;
  /** Version */
  version: number;
  /** Tags */
  tags: string[];
  /** Metadata */
  metadata: Record<string, unknown>;
}

export type WorkflowStatus = 'draft' | 'active' | 'paused' | 'archived' | 'error';

// ── Trigger Types ─────────────────────────────────────────────────────

export interface WorkflowTrigger {
  /** Trigger ID */
  id: string;
  /** Trigger type */
  type: TriggerType;
  /** Trigger name */
  name: string;
  /** Trigger configuration */
  config: TriggerConfig;
  /** Is enabled */
  enabled: boolean;
}

export type TriggerType =
  | 'ticket_created'
  | 'ticket_updated'
  | 'ticket_closed'
  | 'ticket_escalated'
  | 'sla_breach'
  | 'sla_warning'
  | 'customer_message'
  | 'sentiment_change'
  | 'time_based'
  | 'webhook'
  | 'manual'
  | 'api';

export interface TriggerConfig {
  /** Conditions for trigger */
  conditions?: TriggerCondition[];
  /** Schedule (for time-based) */
  schedule?: ScheduleConfig;
  /** Webhook URL (for webhook type) */
  webhook_url?: string;
  /** Webhook secret */
  webhook_secret?: string;
  /** Channel filter */
  channels?: string[];
  /** Priority filter */
  priorities?: string[];
  /** Category filter */
  categories?: string[];
  /** Custom filters */
  custom_filters?: Record<string, unknown>;
}

export interface TriggerCondition {
  /** Field to check */
  field: string;
  /** Operator */
  operator: ConditionOperator;
  /** Value to compare */
  value: unknown;
  /** Logical operator for combining conditions */
  logical_operator?: 'and' | 'or';
}

export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'not_contains'
  | 'starts_with'
  | 'ends_with'
  | 'greater_than'
  | 'less_than'
  | 'greater_or_equal'
  | 'less_or_equal'
  | 'is_empty'
  | 'is_not_empty'
  | 'in'
  | 'not_in';

export interface ScheduleConfig {
  /** Schedule type */
  type: 'once' | 'recurring';
  /** Start date */
  start_date?: Date;
  /** End date */
  end_date?: Date;
  /** Cron expression (for recurring) */
  cron_expression?: string;
  /** Frequency */
  frequency?: 'minutely' | 'hourly' | 'daily' | 'weekly' | 'monthly';
  /** Interval */
  interval?: number;
  /** Time of day */
  time_of_day?: string;
  /** Days of week (for weekly) */
  days_of_week?: number[];
  /** Days of month (for monthly) */
  days_of_month?: number[];
}

// ── Step Types ────────────────────────────────────────────────────────

export interface WorkflowStep {
  /** Step ID */
  id: string;
  /** Step type */
  type: StepType;
  /** Step name */
  name: string;
  /** Step description */
  description?: string;
  /** Step configuration */
  config: StepConfig;
  /** Position in editor */
  position: StepPosition;
  /** Is enabled */
  enabled: boolean;
  /** Error handling */
  error_handling?: ErrorHandlingConfig;
  /** Timeout in seconds */
  timeout_seconds?: number;
  /** Retry configuration */
  retry_config?: RetryConfig;
}

export type StepType =
  | 'action'
  | 'condition'
  | 'delay'
  | 'loop'
  | 'parallel'
  | 'sub_workflow'
  | 'api_call'
  | 'ai_action';

export interface StepPosition {
  /** X coordinate */
  x: number;
  /** Y coordinate */
  y: number;
}

export interface StepConfig {
  /** Action type (for action steps) */
  action_type?: ActionType;
  /** Action parameters */
  action_params?: Record<string, unknown>;
  /** Condition expression (for condition steps) */
  condition?: ConditionExpression;
  /** Delay duration in seconds */
  delay_seconds?: number;
  /** Loop configuration */
  loop_config?: LoopConfig;
  /** Parallel branches */
  parallel_branches?: ParallelBranch[];
  /** Sub-workflow ID */
  sub_workflow_id?: string;
  /** API endpoint */
  api_endpoint?: string;
  /** API method */
  api_method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  /** API headers */
  api_headers?: Record<string, string>;
  /** API body */
  api_body?: Record<string, unknown>;
  /** AI action type */
  ai_action_type?: AIActionType;
  /** AI parameters */
  ai_params?: Record<string, unknown>;
}

export type ActionType =
  | 'assign_ticket'
  | 'update_ticket'
  | 'close_ticket'
  | 'escalate_ticket'
  | 'add_tag'
  | 'remove_tag'
  | 'send_notification'
  | 'send_email'
  | 'create_task'
  | 'update_customer'
  | 'log_activity'
  | 'webhook'
  | 'set_variable'
  | 'custom_code';

export type AIActionType =
  | 'generate_response'
  | 'summarize'
  | 'extract_info'
  | 'classify'
  | 'translate';

export interface ConditionExpression {
  /** Expression type */
  type: 'simple' | 'compound';
  /** Field to check */
  field?: string;
  /** Operator */
  operator?: ConditionOperator;
  /** Value */
  value?: unknown;
  /** Nested conditions */
  conditions?: ConditionExpression[];
  /** Logical operator */
  logical_operator?: 'and' | 'or';
}

export interface LoopConfig {
  /** Loop type */
  type: 'for_each' | 'while' | 'count';
  /** Iterator variable */
  iterator_var?: string;
  /** Collection to iterate */
  collection?: string;
  /** While condition */
  while_condition?: ConditionExpression;
  /** Count */
  count?: number;
  /** Maximum iterations */
  max_iterations?: number;
}

export interface ParallelBranch {
  /** Branch ID */
  id: string;
  /** Branch name */
  name: string;
  /** Steps in branch */
  steps: WorkflowStep[];
}

export interface ErrorHandlingConfig {
  /** Error handling strategy */
  strategy: 'stop' | 'skip' | 'retry' | 'fallback';
  /** Fallback step ID */
  fallback_step_id?: string;
  /** Error notifications */
  notify_on_error?: boolean;
  /** Notification recipients */
  notification_recipients?: string[];
}

export interface RetryConfig {
  /** Maximum retries */
  max_retries: number;
  /** Retry delay in seconds */
  retry_delay_seconds: number;
  /** Exponential backoff */
  exponential_backoff?: boolean;
  /** Max delay for exponential backoff */
  max_delay_seconds?: number;
}

// ── Connection Types ──────────────────────────────────────────────────

export interface WorkflowConnection {
  /** Connection ID */
  id: string;
  /** Source step ID */
  source_step_id: string;
  /** Target step ID */
  target_step_id: string;
  /** Connection label */
  label?: string;
  /** Condition for conditional connections */
  condition?: ConditionExpression;
  /** Connection type */
  type: 'success' | 'error' | 'condition' | 'default';
}

// ── Variable Types ────────────────────────────────────────────────────

export interface WorkflowVariable {
  /** Variable name */
  name: string;
  /** Variable type */
  type: VariableType;
  /** Default value */
  default_value?: unknown;
  /** Is required */
  required?: boolean;
  /** Description */
  description?: string;
  /** Source */
  source?: 'input' | 'step_output' | 'system';
  /** Source step ID (for step_output) */
  source_step_id?: string;
}

export type VariableType = 'string' | 'number' | 'boolean' | 'array' | 'object' | 'date';

// ── Execution Types ───────────────────────────────────────────────────

export interface WorkflowExecution {
  /** Execution ID */
  id: string;
  /** Workflow ID */
  workflow_id: string;
  /** Tenant ID */
  tenant_id: string;
  /** Execution status */
  status: ExecutionStatus;
  /** Trigger that started execution */
  trigger_type: TriggerType;
  /** Trigger data */
  trigger_data: Record<string, unknown>;
  /** Step executions */
  step_executions: StepExecution[];
  /** Variables at execution time */
  variables: Record<string, unknown>;
  /** Started at */
  started_at: Date;
  /** Completed at */
  completed_at?: Date;
  /** Duration in ms */
  duration_ms?: number;
  /** Error message */
  error_message?: string;
  /** Execution log */
  execution_log: ExecutionLogEntry[];
}

export type ExecutionStatus = 
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timeout';

export interface StepExecution {
  /** Step ID */
  step_id: string;
  /** Step name */
  step_name: string;
  /** Execution status */
  status: ExecutionStatus;
  /** Input data */
  input: Record<string, unknown>;
  /** Output data */
  output?: Record<string, unknown>;
  /** Started at */
  started_at: Date;
  /** Completed at */
  completed_at?: Date;
  /** Duration in ms */
  duration_ms?: number;
  /** Error message */
  error_message?: string;
  /** Retry count */
  retry_count?: number;
}

export interface ExecutionLogEntry {
  /** Timestamp */
  timestamp: Date;
  /** Log level */
  level: 'info' | 'warning' | 'error' | 'debug';
  /** Message */
  message: string;
  /** Step ID */
  step_id?: string;
  /** Additional data */
  data?: Record<string, unknown>;
}

// ── Testing Types ──────────────────────────────────────────────────────

export interface WorkflowTest {
  /** Test ID */
  id: string;
  /** Workflow ID */
  workflow_id: string;
  /** Test name */
  name: string;
  /** Test description */
  description?: string;
  /** Test cases */
  test_cases: TestCase[];
  /** Created at */
  created_at: Date;
  /** Updated at */
  updated_at: Date;
}

export interface TestCase {
  /** Case ID */
  id: string;
  /** Case name */
  name: string;
  /** Input data */
  input: Record<string, unknown>;
  /** Expected outcomes */
  expected_outcomes: ExpectedOutcome[];
  /** Mock data */
  mocks?: MockConfig[];
  /** Timeout in seconds */
  timeout_seconds?: number;
}

export interface ExpectedOutcome {
  /** Step ID */
  step_id?: string;
  /** Expected action type */
  action_type?: ActionType;
  /** Expected result */
  expected_result?: Record<string, unknown>;
  /** Expected status */
  expected_status?: ExecutionStatus;
  /** Assertions */
  assertions?: Assertion[];
}

export interface Assertion {
  /** Field path */
  field: string;
  /** Operator */
  operator: 'equals' | 'contains' | 'matches' | 'exists';
  /** Expected value */
  expected_value: unknown;
}

export interface MockConfig {
  /** Mock type */
  type: 'api' | 'ai' | 'action';
  /** Mock identifier */
  identifier: string;
  /** Mock response */
  response: unknown;
  /** Delay in ms */
  delay_ms?: number;
  /** Should fail */
  should_fail?: boolean;
}

export interface TestResult {
  /** Result ID */
  id: string;
  /** Test ID */
  test_id: string;
  /** Execution ID */
  execution_id: string;
  /** Test case ID */
  test_case_id: string;
  /** Passed */
  passed: boolean;
  /** Actual outcomes */
  actual_outcomes: Record<string, unknown>;
  /** Assertion results */
  assertion_results: AssertionResult[];
  /** Duration in ms */
  duration_ms: number;
  /** Executed at */
  executed_at: Date;
  /** Error message */
  error_message?: string;
}

export interface AssertionResult {
  /** Assertion */
  assertion: Assertion;
  /** Passed */
  passed: boolean;
  /** Actual value */
  actual_value: unknown;
  /** Error message */
  error_message?: string;
}

// ── Visual Editor Types ────────────────────────────────────────────────

export interface EditorState {
  /** Workflow being edited */
  workflow: Workflow;
  /** Selected step ID */
  selected_step_id?: string;
  /** Selected connection ID */
  selected_connection_id?: string;
  /** Zoom level */
  zoom: number;
  /** Pan offset */
  pan_offset: { x: number; y: number };
  /** Undo stack */
  undo_stack: EditorAction[];
  /** Redo stack */
  redo_stack: EditorAction[];
  /** Is dirty */
  is_dirty: boolean;
}

export interface EditorAction {
  /** Action type */
  type: EditorActionType;
  /** Step affected */
  step?: WorkflowStep;
  /** Connection affected */
  connection?: WorkflowConnection;
  /** Previous state */
  previous_state?: unknown;
  /** New state */
  new_state?: unknown;
  /** Timestamp */
  timestamp: Date;
}

export type EditorActionType =
  | 'add_step'
  | 'update_step'
  | 'delete_step'
  | 'move_step'
  | 'add_connection'
  | 'update_connection'
  | 'delete_connection'
  | 'update_trigger'
  | 'add_variable'
  | 'update_variable'
  | 'delete_variable';

// ── Template Types ────────────────────────────────────────────────────

export interface WorkflowTemplate {
  /** Template ID */
  id: string;
  /** Template name */
  name: string;
  /** Description */
  description: string;
  /** Category */
  category: TemplateCategory;
  /** Template workflow */
  workflow: Omit<Workflow, 'id' | 'tenant_id' | 'created_at' | 'updated_at' | 'created_by'>;
  /** Variables required */
  required_variables: string[];
  /** Preview image */
  preview_image?: string;
  /** Popularity score */
  popularity: number;
}

export type TemplateCategory =
  | 'ticket_management'
  | 'customer_service'
  | 'escalation'
  | 'notification'
  | 'ai_automation'
  | 'integration';

// ── Variant Capabilities ─────────────────────────────────────────────

export const AUTOMATION_VARIANT_CAPABILITIES: Record<Variant, {
  automation_enabled: boolean;
  visual_editor_enabled: boolean;
  testing_enabled: boolean;
  max_automations: number;
  max_workflow_steps: number;
  max_test_cases: number;
  parallel_execution: boolean;
  ai_actions: boolean;
  custom_code: boolean;
}> = {
  mini_parwa: {
    automation_enabled: false,
    visual_editor_enabled: false,
    testing_enabled: false,
    max_automations: 0,
    max_workflow_steps: 0,
    max_test_cases: 0,
    parallel_execution: false,
    ai_actions: false,
    custom_code: false,
  },
  parwa: {
    automation_enabled: true,
    visual_editor_enabled: true,
    testing_enabled: true,
    max_automations: 25,
    max_workflow_steps: 20,
    max_test_cases: 10,
    parallel_execution: false,
    ai_actions: true,
    custom_code: false,
  },
  parwa_high: {
    automation_enabled: true,
    visual_editor_enabled: true,
    testing_enabled: true,
    max_automations: 100,
    max_workflow_steps: 50,
    max_test_cases: 50,
    parallel_execution: true,
    ai_actions: true,
    custom_code: true,
  },
};
