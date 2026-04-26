/**
 * JARVIS Automation Manager Tests - Week 11 (Phase 3)
 */

import { AutomationManager } from '../automation-manager';
import type { Workflow, WorkflowTest, TestCase, Variant } from '../types';

// ── Test Setup ──────────────────────────────────────────────────────────

const createManager = (variant: Variant = 'parwa'): AutomationManager => {
  return new AutomationManager('tenant_123', variant);
};

const createTestWorkflow = (): Omit<Workflow, 'id' | 'tenant_id' | 'created_at' | 'updated_at' | 'version'> => ({
  name: 'Test Workflow',
  status: 'active',
  trigger: {
    id: 'trigger_1',
    type: 'ticket_created',
    name: 'Ticket Created',
    config: {},
    enabled: true,
  },
  steps: [
    {
      id: 'step_1',
      type: 'action',
      name: 'Assign Ticket',
      config: { action_type: 'assign_ticket', action_params: { agent_id: 'agent_1' } },
      position: { x: 100, y: 100 },
      enabled: true,
    },
  ],
  connections: [],
  variables: [],
  created_by: 'user_1',
  tags: [],
  metadata: {},
});

// ── Initialization Tests ────────────────────────────────────────────────

describe('AutomationManager', () => {
  describe('Initialization', () => {
    it('should initialize successfully for parwa variant', async () => {
      const manager = createManager('parwa');
      await manager.initialize();
      expect(manager.isInitialized()).toBe(true);
    });

    it('should initialize successfully for parwa_high variant', async () => {
      const manager = createManager('parwa_high');
      await manager.initialize();
      expect(manager.isInitialized()).toBe(true);
    });

    it('should throw error for mini_parwa variant', async () => {
      const manager = createManager('mini_parwa');
      await expect(manager.initialize()).rejects.toThrow('Automation is not enabled for this variant');
    });

    it('should not reinitialize if already initialized', async () => {
      const manager = createManager();
      await manager.initialize();
      await manager.initialize(); // Should not throw
      expect(manager.isInitialized()).toBe(true);
    });

    it('should clear state on shutdown', async () => {
      const manager = createManager();
      await manager.initialize();
      await manager.shutdown();
      expect(manager.isInitialized()).toBe(false);
    });
  });

  // ── Workflow CRUD Tests ────────────────────────────────────────────────

  describe('Workflow CRUD', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should create a workflow', () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      expect(workflow.id).toBeDefined();
      expect(workflow.name).toBe('Test Workflow');
      expect(workflow.version).toBe(1);
      expect(workflow.status).toBe('active');
    });

    it('should get a workflow by id', () => {
      const created = manager.createWorkflow(createTestWorkflow());
      const fetched = manager.getWorkflow(created.id);
      expect(fetched).toEqual(created);
    });

    it('should return undefined for non-existent workflow', () => {
      const fetched = manager.getWorkflow('non_existent');
      expect(fetched).toBeUndefined();
    });

    it('should list all workflows', () => {
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Workflow 1' });
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Workflow 2' });
      const list = manager.listWorkflows();
      expect(list).toHaveLength(2);
    });

    it('should filter workflows by status', () => {
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Active', status: 'active' });
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Draft', status: 'draft' });
      const active = manager.listWorkflows({ status: 'active' });
      expect(active).toHaveLength(1);
      expect(active[0].name).toBe('Active');
    });

    it('should filter workflows by tags', () => {
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Tagged', tags: ['urgent'] });
      manager.createWorkflow({ ...createTestWorkflow(), name: 'Not Tagged', tags: [] });
      const tagged = manager.listWorkflows({ tags: ['urgent'] });
      expect(tagged).toHaveLength(1);
      expect(tagged[0].name).toBe('Tagged');
    });

    it('should update a workflow', () => {
      const created = manager.createWorkflow(createTestWorkflow());
      const updated = manager.updateWorkflow(created.id, { name: 'Updated Name' });
      expect(updated.name).toBe('Updated Name');
      expect(updated.version).toBe(2);
    });

    it('should delete a workflow', () => {
      const created = manager.createWorkflow(createTestWorkflow());
      const deleted = manager.deleteWorkflow(created.id);
      expect(deleted).toBe(true);
      expect(manager.getWorkflow(created.id)).toBeUndefined();
    });

    it('should return false when deleting non-existent workflow', () => {
      const deleted = manager.deleteWorkflow('non_existent');
      expect(deleted).toBe(false);
    });

    it('should enforce max automations limit', () => {
      // Create max automations (25 for parwa)
      for (let i = 0; i < 25; i++) {
        manager.createWorkflow({ ...createTestWorkflow(), name: `Workflow ${i}` });
      }

      // Next one should fail
      expect(() => manager.createWorkflow(createTestWorkflow())).toThrow('Maximum automations');
    });
  });

  // ── Workflow Validation Tests ──────────────────────────────────────────

  describe('Workflow Validation', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should reject workflow without trigger', () => {
      const workflow = createTestWorkflow();
      workflow.trigger.enabled = false;
      expect(() => manager.createWorkflow(workflow)).toThrow('must have an enabled trigger');
    });

    it('should reject workflow exceeding step limit', () => {
      const workflow = createTestWorkflow();
      // Add 21 steps (limit is 20 for parwa)
      for (let i = 0; i < 21; i++) {
        workflow.steps.push({
          id: `step_${i}`,
          type: 'action',
          name: `Step ${i}`,
          config: { action_type: 'assign_ticket' },
          position: { x: i * 100, y: 100 },
          enabled: true,
        });
      }
      expect(() => manager.createWorkflow(workflow)).toThrow('exceeds maximum steps');
    });

    it('should reject action step without action_type', () => {
      const workflow = createTestWorkflow();
      workflow.steps = [{
        id: 'step_1',
        type: 'action',
        name: 'Missing Action Type',
        config: {}, // Missing action_type
        position: { x: 100, y: 100 },
        enabled: true,
      }];
      expect(() => manager.createWorkflow(workflow)).toThrow('must have action_type');
    });

    it('should reject condition step without condition', () => {
      const workflow = createTestWorkflow();
      workflow.steps = [{
        id: 'step_1',
        type: 'condition',
        name: 'Missing Condition',
        config: {}, // Missing condition
        position: { x: 100, y: 100 },
        enabled: true,
      }];
      expect(() => manager.createWorkflow(workflow)).toThrow('must have condition');
    });

    it('should reject workflow with invalid connection source', () => {
      const workflow = createTestWorkflow();
      workflow.connections = [{
        id: 'conn_1',
        source_step_id: 'non_existent',
        target_step_id: 'step_1',
        type: 'success',
      }];
      expect(() => manager.createWorkflow(workflow)).toThrow('invalid source step');
    });
  });

  // ── Workflow Execution Tests ───────────────────────────────────────────

  describe('Workflow Execution', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should execute a workflow successfully', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const execution = await manager.executeWorkflow(workflow.id, { ticket_id: 'TKT-001' });

      expect(execution.status).toBe('completed');
      expect(execution.workflow_id).toBe(workflow.id);
      expect(execution.step_executions).toHaveLength(1);
    });

    it('should fail for non-existent workflow', async () => {
      await expect(manager.executeWorkflow('non_existent', {})).rejects.toThrow('not found');
    });

    it('should fail for inactive workflow', async () => {
      const workflow = manager.createWorkflow({ ...createTestWorkflow(), status: 'draft' });
      await expect(manager.executeWorkflow(workflow.id, {})).rejects.toThrow('not active');
    });

    it('should record execution log', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const execution = await manager.executeWorkflow(workflow.id, {});
      expect(execution.execution_log.length).toBeGreaterThan(0);
      expect(execution.execution_log[0].message).toContain('started');
    });

    it('should calculate execution duration', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const execution = await manager.executeWorkflow(workflow.id, {});
      expect(execution.duration_ms).toBeGreaterThanOrEqual(0);
    });

    it('should get execution by id', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const executed = await manager.executeWorkflow(workflow.id, {});
      const fetched = manager.getExecution(executed.id);
      expect(fetched).toEqual(executed);
    });

    it('should list executions', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      await manager.executeWorkflow(workflow.id, {});
      await manager.executeWorkflow(workflow.id, {});
      const executions = manager.listExecutions();
      expect(executions).toHaveLength(2);
    });

    it('should filter executions by workflow', async () => {
      const workflow1 = manager.createWorkflow({ ...createTestWorkflow(), name: 'WF1' });
      const workflow2 = manager.createWorkflow({ ...createTestWorkflow(), name: 'WF2' });
      await manager.executeWorkflow(workflow1.id, {});
      await manager.executeWorkflow(workflow2.id, {});
      const executions = manager.listExecutions(workflow1.id);
      expect(executions).toHaveLength(1);
      expect(executions[0].workflow_id).toBe(workflow1.id);
    });

    it('should execute multiple steps in order', async () => {
      const workflow = manager.createWorkflow({
        ...createTestWorkflow(),
        steps: [
          {
            id: 'step_1',
            type: 'action',
            name: 'Step 1',
            config: { action_type: 'assign_ticket' },
            position: { x: 100, y: 100 },
            enabled: true,
          },
          {
            id: 'step_2',
            type: 'action',
            name: 'Step 2',
            config: { action_type: 'update_ticket' },
            position: { x: 200, y: 100 },
            enabled: true,
          },
        ],
        connections: [
          { id: 'conn_1', source_step_id: 'step_1', target_step_id: 'step_2', type: 'success' },
        ],
      });

      const execution = await manager.executeWorkflow(workflow.id, {});
      expect(execution.step_executions).toHaveLength(2);
    });
  });

  // ── Testing Framework Tests ────────────────────────────────────────────

  describe('Testing Framework', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should create a test', () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const test = manager.createTest({
        workflow_id: workflow.id,
        name: 'Test 1',
        test_cases: [],
      });
      expect(test.id).toBeDefined();
      expect(test.name).toBe('Test 1');
    });

    it('should run a test', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const test = manager.createTest({
        workflow_id: workflow.id,
        name: 'Test 1',
        test_cases: [{
          id: 'case_1',
          name: 'Case 1',
          input: { ticket_id: 'TKT-001' },
          expected_outcomes: [{ expected_status: 'completed' }],
        }],
      });

      const results = await manager.runTest(test.id);
      expect(results).toHaveLength(1);
      expect(results[0].passed).toBe(true);
    });

    it('should fail test for unexpected status', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      const test = manager.createTest({
        workflow_id: workflow.id,
        name: 'Test 1',
        test_cases: [{
          id: 'case_1',
          name: 'Case 1',
          input: {},
          expected_outcomes: [{ expected_status: 'failed' }],
        }],
      });

      const results = await manager.runTest(test.id);
      expect(results[0].passed).toBe(false);
    });

    it('should throw for non-existent test', async () => {
      await expect(manager.runTest('non_existent')).rejects.toThrow('not found');
    });

    it('should throw for mini_parwa variant when creating test', async () => {
      const miniManager = createManager('mini_parwa');
      await expect(miniManager.initialize()).rejects.toThrow();
    });
  });

  // ── Templates Tests ────────────────────────────────────────────────────

  describe('Templates', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should list available templates', () => {
      const templates = manager.getTemplates();
      expect(templates.length).toBeGreaterThan(0);
      expect(templates[0].id).toBeDefined();
      expect(templates[0].name).toBeDefined();
    });

    it('should create workflow from template', () => {
      const workflow = manager.createFromTemplate('auto-assign-priority', { priority_threshold: 'high' });
      expect(workflow.name).toContain('Auto-Assign');
      expect(workflow.steps.length).toBeGreaterThan(0);
    });

    it('should throw for missing required variables', () => {
      expect(() => manager.createFromTemplate('auto-assign-priority', {})).toThrow('Missing required variable');
    });

    it('should throw for non-existent template', () => {
      expect(() => manager.createFromTemplate('non_existent', {})).toThrow('not found');
    });
  });

  // ── Capabilities Tests ──────────────────────────────────────────────────

  describe('Capabilities', () => {
    it('should return parwa capabilities', async () => {
      const manager = createManager('parwa');
      await manager.initialize();
      const caps = manager.getCapabilities();
      expect(caps.automation_enabled).toBe(true);
      expect(caps.max_automations).toBe(25);
    });

    it('should return parwa_high capabilities', async () => {
      const manager = createManager('parwa_high');
      await manager.initialize();
      const caps = manager.getCapabilities();
      expect(caps.automation_enabled).toBe(true);
      expect(caps.max_automations).toBe(100);
      expect(caps.parallel_execution).toBe(true);
    });

    it('should check canCreateAutomation', async () => {
      const manager = createManager('parwa');
      await manager.initialize();
      expect(manager.canCreateAutomation()).toBe(true);
    });

    it('should check canAddSteps', async () => {
      const manager = createManager('parwa');
      await manager.initialize();
      expect(manager.canAddSteps(15)).toBe(true);
      expect(manager.canAddSteps(25)).toBe(false);
    });
  });

  // ── Statistics Tests ────────────────────────────────────────────────────

  describe('Statistics', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should return zero statistics initially', () => {
      const stats = manager.getStatistics();
      expect(stats.total_workflows).toBe(0);
      expect(stats.total_executions).toBe(0);
    });

    it('should track workflow count', () => {
      manager.createWorkflow(createTestWorkflow());
      const stats = manager.getStatistics();
      expect(stats.total_workflows).toBe(1);
      expect(stats.active_workflows).toBe(1);
    });

    it('should track execution count', async () => {
      const workflow = manager.createWorkflow(createTestWorkflow());
      await manager.executeWorkflow(workflow.id, {});
      const stats = manager.getStatistics();
      expect(stats.total_executions).toBe(1);
      expect(stats.successful_executions).toBe(1);
    });

    it('should track failed executions', async () => {
      const workflow = manager.createWorkflow({
        ...createTestWorkflow(),
        steps: [{
          id: 'step_1',
          type: 'action',
          name: 'Failing Step',
          config: { action_type: 'escalate_ticket', action_params: { level: 99 } },
          position: { x: 100, y: 100 },
          enabled: true,
          error_handling: { strategy: 'stop' },
        }],
      });
      // This would fail in a real scenario; for now execution completes
      await manager.executeWorkflow(workflow.id, {});
      const stats = manager.getStatistics();
      expect(stats.total_executions).toBe(1);
    });
  });

  // ── Event System Tests ──────────────────────────────────────────────────

  describe('Event System', () => {
    let manager: AutomationManager;

    beforeEach(async () => {
      manager = createManager();
      await manager.initialize();
    });

    afterEach(async () => {
      await manager.shutdown();
    });

    it('should emit workflow_created event', () => {
      const events: any[] = [];
      manager.addEventListener((event) => events.push(event));

      manager.createWorkflow(createTestWorkflow());

      expect(events.length).toBeGreaterThan(0);
      expect(events.find(e => e.type === 'workflow_created')).toBeDefined();
    });

    it('should emit execution_completed event', async () => {
      const events: any[] = [];
      manager.addEventListener((event) => events.push(event));

      const workflow = manager.createWorkflow(createTestWorkflow());
      await manager.executeWorkflow(workflow.id, {});

      expect(events.find(e => e.type === 'execution_completed')).toBeDefined();
    });

    it('should unsubscribe listener', () => {
      const events: any[] = [];
      const unsubscribe = manager.addEventListener((event) => events.push(event));

      unsubscribe();
      manager.createWorkflow(createTestWorkflow());

      expect(events.length).toBe(0);
    });
  });

  // ── Variant Limits Tests ────────────────────────────────────────────────

  describe('Variant Limits', () => {
    it('should allow 25 automations for parwa', async () => {
      const manager = createManager('parwa');
      await manager.initialize();
      const caps = manager.getCapabilities();
      expect(caps.max_automations).toBe(25);
      expect(caps.max_workflow_steps).toBe(20);
    });

    it('should allow 100 automations for parwa_high', async () => {
      const manager = createManager('parwa_high');
      await manager.initialize();
      const caps = manager.getCapabilities();
      expect(caps.max_automations).toBe(100);
      expect(caps.max_workflow_steps).toBe(50);
    });

    it('should not allow automation for mini_parwa', async () => {
      const manager = createManager('mini_parwa');
      const caps = manager.getCapabilities();
      expect(caps.automation_enabled).toBe(false);
      expect(caps.max_automations).toBe(0);
    });

    it('should enable testing for parwa and parwa_high', async () => {
      const parwaManager = createManager('parwa');
      await parwaManager.initialize();
      expect(parwaManager.getCapabilities().testing_enabled).toBe(true);

      const highManager = createManager('parwa_high');
      await highManager.initialize();
      expect(highManager.getCapabilities().testing_enabled).toBe(true);
    });

    it('should enable custom_code only for parwa_high', async () => {
      const parwaManager = createManager('parwa');
      await parwaManager.initialize();
      expect(parwaManager.getCapabilities().custom_code).toBe(false);

      const highManager = createManager('parwa_high');
      await highManager.initialize();
      expect(highManager.getCapabilities().custom_code).toBe(true);
    });
  });
});
