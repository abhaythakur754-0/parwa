/**
 * JARVIS Automation Manager - Week 11 (Phase 3)
 *
 * Visual workflow builder for custom automations with triggers, actions, and testing.
 */

import type { Variant } from '@/types/variant';
import type {
  AutomationConfig,
  Workflow,
  WorkflowStatus,
  WorkflowTrigger,
  WorkflowStep,
  WorkflowConnection,
  WorkflowExecution,
  ExecutionStatus,
  WorkflowTest,
  TestCase,
  TestResult,
  WorkflowTemplate,
  TriggerType,
  ActionType,
  StepType,
  ConditionOperator,
  AUTOMATION_VARIANT_CAPABILITIES,
} from './types';
import { DEFAULT_AUTOMATION_CONFIG, AUTOMATION_VARIANT_CAPABILITIES as CAPABILITIES } from './types';

// ── Event Types ────────────────────────────────────────────────────────

export interface AutomationEvent {
  type: 'workflow_created' | 'workflow_updated' | 'workflow_deleted' | 'workflow_executed' |
        'execution_started' | 'execution_completed' | 'execution_failed' | 'test_completed';
  workflow_id?: string;
  execution_id?: string;
  data: Record<string, unknown>;
  timestamp: Date;
}

export type AutomationEventListener = (event: AutomationEvent) => void;

// ── Automation Manager ──────────────────────────────────────────────────

export class AutomationManager {
  private tenantId: string;
  private variant: Variant;
  private config: AutomationConfig;
  private workflows: Map<string, Workflow> = new Map();
  private executions: Map<string, WorkflowExecution> = new Map();
  private tests: Map<string, WorkflowTest> = new Map();
  private eventListeners: Set<AutomationEventListener> = new Set();
  private initialized: boolean = false;

  constructor(tenantId: string, variant: Variant) {
    this.tenantId = tenantId;
    this.variant = variant;
    this.config = this.buildConfig(variant);
  }

  private buildConfig(variant: Variant): AutomationConfig {
    const defaults = DEFAULT_AUTOMATION_CONFIG[variant] || {};
    return {
      tenant_id: this.tenantId,
      variant,
      automation_enabled: defaults.automation_enabled ?? false,
      max_automations: defaults.max_automations ?? 0,
      visual_editor_enabled: defaults.visual_editor_enabled ?? false,
      testing_enabled: defaults.testing_enabled ?? false,
      max_workflow_steps: defaults.max_workflow_steps ?? 0,
      execution_timeout_seconds: 300,
    };
  }

  // ── Initialization ───────────────────────────────────────────────────

  async initialize(): Promise<void> {
    if (this.initialized) return;

    if (!this.config.automation_enabled) {
      throw new Error('Automation is not enabled for this variant');
    }

    this.initialized = true;
    this.emitEvent({ type: 'workflow_created', data: { action: 'initialized' } });
  }

  isInitialized(): boolean {
    return this.initialized;
  }

  async shutdown(): Promise<void> {
    this.workflows.clear();
    this.executions.clear();
    this.tests.clear();
    this.eventListeners.clear();
    this.initialized = false;
  }

  // ── Workflow CRUD ─────────────────────────────────────────────────────

  createWorkflow(workflow: Omit<Workflow, 'id' | 'tenant_id' | 'created_at' | 'updated_at' | 'version'>): Workflow {
    this.ensureInitialized();
    this.ensureCapacity();

    const id = this.generateId('wf');
    const now = new Date();

    const newWorkflow: Workflow = {
      ...workflow,
      id,
      tenant_id: this.tenantId,
      created_at: now,
      updated_at: now,
      version: 1,
    };

    // Validate workflow
    this.validateWorkflow(newWorkflow);

    this.workflows.set(id, newWorkflow);

    this.emitEvent({
      type: 'workflow_created',
      workflow_id: id,
      data: { name: workflow.name },
    });

    return newWorkflow;
  }

  getWorkflow(workflowId: string): Workflow | undefined {
    return this.workflows.get(workflowId);
  }

  listWorkflows(filters?: { status?: WorkflowStatus; tags?: string[] }): Workflow[] {
    const workflows = Array.from(this.workflows.values());

    if (!filters) return workflows;

    return workflows.filter(w => {
      if (filters.status && w.status !== filters.status) return false;
      if (filters.tags && filters.tags.length > 0) {
        const hasTag = filters.tags.some(tag => w.tags.includes(tag));
        if (!hasTag) return false;
      }
      return true;
    });
  }

  updateWorkflow(workflowId: string, updates: Partial<Workflow>): Workflow {
    this.ensureInitialized();

    const existing = this.workflows.get(workflowId);
    if (!existing) {
      throw new Error(`Workflow ${workflowId} not found`);
    }

    const updated: Workflow = {
      ...existing,
      ...updates,
      id: existing.id,
      tenant_id: existing.tenant_id,
      created_at: existing.created_at,
      updated_at: new Date(),
      version: existing.version + 1,
    };

    this.validateWorkflow(updated);
    this.workflows.set(workflowId, updated);

    this.emitEvent({
      type: 'workflow_updated',
      workflow_id: workflowId,
      data: { name: updated.name, version: updated.version },
    });

    return updated;
  }

  deleteWorkflow(workflowId: string): boolean {
    this.ensureInitialized();

    const existed = this.workflows.delete(workflowId);

    if (existed) {
      this.emitEvent({
        type: 'workflow_deleted',
        workflow_id: workflowId,
        data: {},
      });
    }

    return existed;
  }

  // ── Workflow Execution ─────────────────────────────────────────────────

  async executeWorkflow(
    workflowId: string,
    triggerData: Record<string, unknown>,
    triggerType: TriggerType = 'manual'
  ): Promise<WorkflowExecution> {
    this.ensureInitialized();

    const workflow = this.workflows.get(workflowId);
    if (!workflow) {
      throw new Error(`Workflow ${workflowId} not found`);
    }

    if (workflow.status !== 'active') {
      throw new Error(`Workflow ${workflowId} is not active`);
    }

    const executionId = this.generateId('exec');
    const execution: WorkflowExecution = {
      id: executionId,
      workflow_id: workflowId,
      tenant_id: this.tenantId,
      status: 'pending',
      trigger_type: triggerType,
      trigger_data: triggerData,
      step_executions: [],
      variables: {},
      started_at: new Date(),
      execution_log: [],
    };

    this.executions.set(executionId, execution);

    this.emitEvent({
      type: 'execution_started',
      workflow_id: workflowId,
      execution_id: executionId,
      data: { trigger_type: triggerType },
    });

    try {
      execution.status = 'running';
      this.addLog(execution, 'info', 'Workflow execution started');

      // Execute steps in order
      const stepMap = new Map(workflow.steps.map(s => [s.id, s]));
      const connectionMap = this.buildConnectionMap(workflow.connections);

      // Find entry point (first step or trigger-connected step)
      let currentStepId = this.findEntryPoint(workflow);

      while (currentStepId) {
        const step = stepMap.get(currentStepId);
        if (!step || !step.enabled) {
          currentStepId = this.getNextStep(connectionMap, currentStepId, 'success');
          continue;
        }

        const stepExecution = await this.executeStep(execution, step, triggerData);
        execution.step_executions.push(stepExecution);

        if (stepExecution.status === 'failed') {
          execution.status = 'failed';
          execution.error_message = stepExecution.error_message;
          this.addLog(execution, 'error', `Step ${step.name} failed: ${stepExecution.error_message}`, step.id);
          break;
        }

        currentStepId = this.getNextStep(connectionMap, currentStepId, 'success');
      }

      if (execution.status === 'running') {
        execution.status = 'completed';
      }
    } catch (error) {
      execution.status = 'failed';
      execution.error_message = error instanceof Error ? error.message : 'Unknown error';
      this.addLog(execution, 'error', execution.error_message);
    }

    execution.completed_at = new Date();
    execution.duration_ms = execution.completed_at.getTime() - execution.started_at.getTime();

    this.emitEvent({
      type: execution.status === 'completed' ? 'execution_completed' : 'execution_failed',
      workflow_id: workflowId,
      execution_id: executionId,
      data: { status: execution.status, duration_ms: execution.duration_ms },
    });

    return execution;
  }

  getExecution(executionId: string): WorkflowExecution | undefined {
    return this.executions.get(executionId);
  }

  listExecutions(workflowId?: string): WorkflowExecution[] {
    const executions = Array.from(this.executions.values());
    if (workflowId) {
      return executions.filter(e => e.workflow_id === workflowId);
    }
    return executions;
  }

  // ── Testing Framework ──────────────────────────────────────────────────

  createTest(test: Omit<WorkflowTest, 'id' | 'created_at' | 'updated_at'>): WorkflowTest {
    this.ensureInitialized();
    this.ensureTestingEnabled();

    const id = this.generateId('test');
    const now = new Date();

    const newTest: WorkflowTest = {
      ...test,
      id,
      created_at: now,
      updated_at: now,
    };

    this.tests.set(id, newTest);
    return newTest;
  }

  async runTest(testId: string): Promise<TestResult[]> {
    this.ensureInitialized();
    this.ensureTestingEnabled();

    const test = this.tests.get(testId);
    if (!test) {
      throw new Error(`Test ${testId} not found`);
    }

    const results: TestResult[] = [];

    for (const testCase of test.test_cases) {
      const result = await this.runTestCase(test.workflow_id, testCase);
      results.push(result);
    }

    this.emitEvent({
      type: 'test_completed',
      workflow_id: test.workflow_id,
      data: { test_id: testId, passed: results.every(r => r.passed) },
    });

    return results;
  }

  private async runTestCase(workflowId: string, testCase: TestCase): Promise<TestResult> {
    const execution = await this.executeWorkflow(workflowId, testCase.input, 'manual');

    const result: TestResult = {
      id: this.generateId('result'),
      test_id: workflowId,
      execution_id: execution.id,
      test_case_id: testCase.id,
      passed: execution.status === 'completed',
      actual_outcomes: { status: execution.status },
      assertion_results: [],
      duration_ms: execution.duration_ms || 0,
      executed_at: new Date(),
    };

    // Check assertions
    for (const outcome of testCase.expected_outcomes) {
      if (outcome.expected_status && execution.status !== outcome.expected_status) {
        result.passed = false;
        result.error_message = `Expected status ${outcome.expected_status} but got ${execution.status}`;
      }
    }

    return result;
  }

  // ── Templates ──────────────────────────────────────────────────────────

  getTemplates(): WorkflowTemplate[] {
    return [
      {
        id: 'auto-assign-priority',
        name: 'Auto-Assign Priority Tickets',
        description: 'Automatically assign high-priority tickets to senior agents',
        category: 'ticket_management',
        workflow: this.createTemplateWorkflow('auto-assign-priority'),
        required_variables: ['priority_threshold'],
        popularity: 95,
      },
      {
        id: 'sla-escalation',
        name: 'SLA Breach Escalation',
        description: 'Escalate tickets before SLA breach',
        category: 'escalation',
        workflow: this.createTemplateWorkflow('sla-escalation'),
        required_variables: ['sla_threshold_minutes'],
        popularity: 90,
      },
      {
        id: 'customer-satisfaction-followup',
        name: 'CSAT Follow-up',
        description: 'Send follow-up for low satisfaction scores',
        category: 'customer_service',
        workflow: this.createTemplateWorkflow('customer-satisfaction-followup'),
        required_variables: ['csat_threshold'],
        popularity: 85,
      },
    ];
  }

  createFromTemplate(templateId: string, variables: Record<string, unknown>): Workflow {
    const template = this.getTemplates().find(t => t.id === templateId);
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }

    // Validate required variables
    for (const varName of template.required_variables) {
      if (!(varName in variables)) {
        throw new Error(`Missing required variable: ${varName}`);
      }
    }

    return this.createWorkflow({
      ...template.workflow,
      name: `${template.name} (Copy)`,
      variables: template.workflow.variables.map(v => ({
        ...v,
        default_value: variables[v.name] ?? v.default_value,
      })),
    });
  }

  // ── Capabilities ───────────────────────────────────────────────────────

  getCapabilities(): typeof CAPABILITIES[Variant] {
    return CAPABILITIES[this.variant];
  }

  canCreateAutomation(): boolean {
    return this.config.automation_enabled && this.workflows.size < this.config.max_automations;
  }

  canAddSteps(currentSteps: number): boolean {
    return currentSteps < this.config.max_workflow_steps;
  }

  // ── Statistics ─────────────────────────────────────────────────────────

  getStatistics(): {
    total_workflows: number;
    active_workflows: number;
    total_executions: number;
    successful_executions: number;
    failed_executions: number;
    average_execution_time_ms: number;
  } {
    const workflows = Array.from(this.workflows.values());
    const executions = Array.from(this.executions.values());

    const successful = executions.filter(e => e.status === 'completed');
    const failed = executions.filter(e => e.status === 'failed');
    const avgTime = executions.length > 0
      ? executions.reduce((sum, e) => sum + (e.duration_ms || 0), 0) / executions.length
      : 0;

    return {
      total_workflows: workflows.length,
      active_workflows: workflows.filter(w => w.status === 'active').length,
      total_executions: executions.length,
      successful_executions: successful.length,
      failed_executions: failed.length,
      average_execution_time_ms: avgTime,
    };
  }

  // ── Event System ────────────────────────────────────────────────────────

  addEventListener(listener: AutomationEventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  private emitEvent(event: AutomationEvent): void {
    const fullEvent: AutomationEvent = {
      ...event,
      timestamp: new Date(),
    };

    for (const listener of this.eventListeners) {
      try {
        listener(fullEvent);
      } catch (error) {
        console.error('[AutomationManager] Event listener error:', error);
      }
    }
  }

  // ── Private Helpers ────────────────────────────────────────────────────

  private ensureInitialized(): void {
    if (!this.initialized) {
      throw new Error('AutomationManager not initialized');
    }
  }

  private ensureCapacity(): void {
    if (this.workflows.size >= this.config.max_automations) {
      throw new Error(`Maximum automations (${this.config.max_automations}) reached`);
    }
  }

  private ensureTestingEnabled(): void {
    if (!this.config.testing_enabled) {
      throw new Error('Testing is not enabled for this variant');
    }
  }

  private validateWorkflow(workflow: Workflow): void {
    // Check step limit
    if (workflow.steps.length > this.config.max_workflow_steps) {
      throw new Error(`Workflow exceeds maximum steps (${this.config.max_workflow_steps})`);
    }

    // Validate trigger
    if (!workflow.trigger || !workflow.trigger.enabled) {
      throw new Error('Workflow must have an enabled trigger');
    }

    // Validate steps
    for (const step of workflow.steps) {
      this.validateStep(step);
    }

    // Validate connections reference valid steps
    const stepIds = new Set(workflow.steps.map(s => s.id));
    for (const conn of workflow.connections) {
      if (!stepIds.has(conn.source_step_id)) {
        throw new Error(`Connection references invalid source step: ${conn.source_step_id}`);
      }
      if (!stepIds.has(conn.target_step_id)) {
        throw new Error(`Connection references invalid target step: ${conn.target_step_id}`);
      }
    }
  }

  private validateStep(step: WorkflowStep): void {
    if (!step.id || !step.name) {
      throw new Error('Step must have id and name');
    }

    if (step.type === 'action' && !step.config.action_type) {
      throw new Error(`Action step ${step.name} must have action_type`);
    }

    if (step.type === 'condition' && !step.config.condition) {
      throw new Error(`Condition step ${step.name} must have condition`);
    }
  }

  private async executeStep(
    execution: WorkflowExecution,
    step: WorkflowStep,
    triggerData: Record<string, unknown>
  ): Promise<WorkflowExecution['step_executions'][0]> {
    const stepExecution: WorkflowExecution['step_executions'][0] = {
      step_id: step.id,
      step_name: step.name,
      status: 'running',
      input: triggerData,
      started_at: new Date(),
    };

    this.addLog(execution, 'info', `Executing step: ${step.name}`, step.id);

    try {
      // Simulate step execution based on type
      const output = await this.performStepAction(step, triggerData);
      stepExecution.output = output;
      stepExecution.status = 'completed';
      this.addLog(execution, 'info', `Step ${step.name} completed`, step.id);
    } catch (error) {
      stepExecution.status = 'failed';
      stepExecution.error_message = error instanceof Error ? error.message : 'Unknown error';
      this.addLog(execution, 'error', `Step ${step.name} failed: ${stepExecution.error_message}`, step.id);

      // Handle error based on error_handling config
      if (step.error_handling?.strategy === 'skip') {
        stepExecution.status = 'completed';
        stepExecution.output = { skipped: true, error: stepExecution.error_message };
      }
    }

    stepExecution.completed_at = new Date();
    stepExecution.duration_ms = stepExecution.completed_at.getTime() - stepExecution.started_at.getTime();

    return stepExecution;
  }

  private async performStepAction(
    step: WorkflowStep,
    _triggerData: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    // Simulate action execution
    switch (step.config.action_type) {
      case 'assign_ticket':
        return { assigned: true, agent_id: step.config.action_params?.agent_id };
      case 'update_ticket':
        return { updated: true, fields: step.config.action_params?.fields };
      case 'close_ticket':
        return { closed: true };
      case 'escalate_ticket':
        return { escalated: true, level: step.config.action_params?.level };
      case 'add_tag':
        return { tagged: true, tags: step.config.action_params?.tags };
      case 'send_notification':
        return { notified: true, recipients: step.config.action_params?.recipients };
      case 'send_email':
        return { email_sent: true, to: step.config.action_params?.to };
      default:
        return { action_performed: step.config.action_type };
    }
  }

  private buildConnectionMap(connections: WorkflowConnection[]): Map<string, WorkflowConnection[]> {
    const map = new Map<string, WorkflowConnection[]>();
    for (const conn of connections) {
      const existing = map.get(conn.source_step_id) || [];
      existing.push(conn);
      map.set(conn.source_step_id, existing);
    }
    return map;
  }

  private findEntryPoint(workflow: Workflow): string | undefined {
    // Find the first step (connected from trigger or first in list)
    if (workflow.connections.length === 0 && workflow.steps.length > 0) {
      return workflow.steps[0].id;
    }

    // Find step connected from trigger (if such connection exists)
    const triggerConn = workflow.connections.find(c => c.source_step_id === workflow.trigger.id);
    if (triggerConn) {
      return triggerConn.target_step_id;
    }

    // Return first step
    return workflow.steps[0]?.id;
  }

  private getNextStep(
    connectionMap: Map<string, WorkflowConnection[]>,
    currentStepId: string,
    connectionType: 'success' | 'error' | 'condition' | 'default'
  ): string | undefined {
    const connections = connectionMap.get(currentStepId) || [];
    const conn = connections.find(c => c.type === connectionType) || connections.find(c => c.type === 'default');
    return conn?.target_step_id;
  }

  private addLog(
    execution: WorkflowExecution,
    level: 'info' | 'warning' | 'error' | 'debug',
    message: string,
    stepId?: string
  ): void {
    execution.execution_log.push({
      timestamp: new Date(),
      level,
      message,
      step_id: stepId,
    });
  }

  private generateId(prefix: string): string {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
  }

  private createTemplateWorkflow(templateId: string): Omit<Workflow, 'id' | 'tenant_id' | 'created_at' | 'updated_at' | 'created_by'> {
    const baseWorkflow = {
      status: 'draft' as WorkflowStatus,
      connections: [] as WorkflowConnection[],
      variables: [] as Workflow['variables'],
      tags: [] as string[],
      metadata: {} as Record<string, unknown>,
    };

    switch (templateId) {
      case 'auto-assign-priority':
        return {
          ...baseWorkflow,
          name: 'Auto-Assign Priority Tickets',
          description: 'Automatically assign high-priority tickets to senior agents',
          trigger: {
            id: 'trigger_1',
            type: 'ticket_created' as TriggerType,
            name: 'Ticket Created',
            config: { priorities: ['urgent', 'high'] },
            enabled: true,
          },
          steps: [
            {
              id: 'step_1',
              type: 'action' as StepType,
              name: 'Assign to Senior Agent',
              config: { action_type: 'assign_ticket' as ActionType, action_params: { level: 'senior' } },
              position: { x: 100, y: 100 },
              enabled: true,
            },
          ],
        };

      case 'sla-escalation':
        return {
          ...baseWorkflow,
          name: 'SLA Breach Escalation',
          description: 'Escalate tickets before SLA breach',
          trigger: {
            id: 'trigger_1',
            type: 'sla_warning' as TriggerType,
            name: 'SLA Warning',
            config: {},
            enabled: true,
          },
          steps: [
            {
              id: 'step_1',
              type: 'action' as StepType,
              name: 'Escalate Ticket',
              config: { action_type: 'escalate_ticket' as ActionType, action_params: { level: 2 } },
              position: { x: 100, y: 100 },
              enabled: true,
            },
            {
              id: 'step_2',
              type: 'action' as StepType,
              name: 'Send Notification',
              config: { action_type: 'send_notification' as ActionType, action_params: { recipients: ['team_lead'] } },
              position: { x: 100, y: 200 },
              enabled: true,
            },
          ],
        };

      case 'customer-satisfaction-followup':
        return {
          ...baseWorkflow,
          name: 'CSAT Follow-up',
          description: 'Send follow-up for low satisfaction scores',
          trigger: {
            id: 'trigger_1',
            type: 'ticket_closed' as TriggerType,
            name: 'Ticket Closed',
            config: {},
            enabled: true,
          },
          steps: [
            {
              id: 'step_1',
              type: 'condition' as StepType,
              name: 'Check CSAT Score',
              config: {
                condition: {
                  type: 'simple',
                  field: 'csat_score',
                  operator: 'less_than' as ConditionOperator,
                  value: 3,
                },
              },
              position: { x: 100, y: 100 },
              enabled: true,
            },
            {
              id: 'step_2',
              type: 'action' as StepType,
              name: 'Send Follow-up Email',
              config: { action_type: 'send_email' as ActionType, action_params: { template: 'csat_followup' } },
              position: { x: 100, y: 200 },
              enabled: true,
            },
          ],
        };

      default:
        return {
          ...baseWorkflow,
          name: 'New Workflow',
          trigger: {
            id: 'trigger_1',
            type: 'manual' as TriggerType,
            name: 'Manual Trigger',
            config: {},
            enabled: true,
          },
          steps: [],
        };
    }
  }
}

export default AutomationManager;
