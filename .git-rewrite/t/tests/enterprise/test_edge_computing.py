# Tests for Builder 3 - Edge Computing
# Week 51: edge_compute.py, edge_functions.py, edge_orchestrator.py

import pytest
from datetime import datetime, timedelta

from enterprise.global_infra.edge_compute import (
    EdgeCompute, EdgeNode, ComputeRequest, EdgeNodeStatus, ComputeTier
)
from enterprise.global_infra.edge_functions import (
    EdgeFunctions, EdgeFunction, FunctionInvocation, FunctionStatus, Runtime
)
from enterprise.global_infra.edge_orchestrator import (
    EdgeOrchestrator, Workflow, OrchestrationStep, OrchestrationExecution,
    OrchestrationStatus, StepType
)


# =============================================================================
# EDGE COMPUTE TESTS
# =============================================================================

class TestEdgeCompute:
    """Tests for EdgeCompute class"""

    def test_init(self):
        """Test compute initialization"""
        compute = EdgeCompute()
        assert compute is not None
        metrics = compute.get_metrics()
        assert metrics["total_nodes"] == 0

    def test_register_node(self):
        """Test registering a node"""
        compute = EdgeCompute()
        node = compute.register_node(
            name="edge-1",
            region="us-east-1",
            endpoint="https://edge1.example.com",
            tier=ComputeTier.STANDARD
        )
        assert node.name == "edge-1"
        assert node.region == "us-east-1"
        assert node.status == EdgeNodeStatus.ONLINE

    def test_deregister_node(self):
        """Test deregistering a node"""
        compute = EdgeCompute()
        node = compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        result = compute.deregister_node(node.id)
        assert result is True
        assert compute.get_node(node.id) is None

    def test_update_node_status(self):
        """Test updating node status"""
        compute = EdgeCompute()
        node = compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        result = compute.update_node_status(node.id, EdgeNodeStatus.MAINTENANCE)
        assert result is True
        assert node.status == EdgeNodeStatus.MAINTENANCE

    def test_update_node_resources(self):
        """Test updating node resources"""
        compute = EdgeCompute()
        node = compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        result = compute.update_node_resources(node.id, 50.0, 60.0, 10)
        assert result is True
        assert node.available_cpu == 50.0
        assert node.available_memory == 60.0

    def test_get_available_node(self):
        """Test getting available node"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        compute.register_node("edge-2", "eu-west-1", "https://edge2.example.com")

        node = compute.get_available_node(region="us-east-1")
        assert node is not None
        assert node.region == "us-east-1"

    def test_get_available_node_with_requirements(self):
        """Test getting node with resource requirements"""
        compute = EdgeCompute()
        n1 = compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        n2 = compute.register_node("edge-2", "us-east-1", "https://edge2.example.com")

        # n1 has low resources, n2 has high resources
        compute.update_node_resources(n1.id, 30.0, 30.0, 50)  # Low available
        compute.update_node_resources(n2.id, 80.0, 80.0, 5)   # High available

        node = compute.get_available_node(min_cpu=70, min_memory=70)
        assert node is not None
        assert node.available_cpu >= 70

    def test_get_available_node_none_available(self):
        """Test when no node available"""
        compute = EdgeCompute()
        node = compute.get_available_node()
        assert node is None

    def test_execute_request(self):
        """Test executing a request"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")

        request = compute.execute_request(
            function_name="test-func",
            payload={"key": "value"},
            region="us-east-1"
        )
        assert request is not None
        assert request.function_name == "test-func"

    def test_complete_request(self):
        """Test completing a request"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        request = compute.execute_request("test-func", {})

        result = compute.complete_request(request.id, {"result": "ok"}, 100.0, 50.0)
        assert result is True
        assert request.status == "completed"

    def test_fail_request(self):
        """Test failing a request"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        request = compute.execute_request("test-func", {})

        result = compute.fail_request(request.id, "Connection failed")
        assert result is True
        assert request.status == "failed"

    def test_get_nodes_by_region(self):
        """Test getting nodes by region"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")
        compute.register_node("edge-2", "us-east-1", "https://edge2.example.com")
        compute.register_node("edge-3", "eu-west-1", "https://edge3.example.com")

        nodes = compute.get_nodes_by_region("us-east-1")
        assert len(nodes) == 2

    def test_get_metrics(self):
        """Test getting metrics"""
        compute = EdgeCompute()
        compute.register_node("edge-1", "us-east-1", "https://edge1.example.com")

        metrics = compute.get_metrics()
        assert metrics["total_nodes"] == 1
        assert metrics["online_nodes"] == 1


# =============================================================================
# EDGE FUNCTIONS TESTS
# =============================================================================

class TestEdgeFunctions:
    """Tests for EdgeFunctions class"""

    def test_init(self):
        """Test functions initialization"""
        functions = EdgeFunctions()
        assert functions is not None
        metrics = functions.get_metrics()
        assert metrics["total_functions"] == 0

    def test_create_function(self):
        """Test creating a function"""
        functions = EdgeFunctions()
        func = functions.create_function(
            name="hello-world",
            runtime=Runtime.PYTHON,
            code="def handler(event): return {'message': 'Hello'}"
        )
        assert func.name == "hello-world"
        assert func.runtime == Runtime.PYTHON
        assert func.status == FunctionStatus.CREATED

    def test_update_function(self):
        """Test updating a function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        result = functions.update_function(func.id, memory_mb=256)
        assert result is True
        assert func.memory_mb == 256

    def test_delete_function(self):
        """Test deleting a function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        result = functions.delete_function(func.id)
        assert result is True
        assert functions.get_function(func.id) is None

    def test_deploy_function(self):
        """Test deploying a function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        result = functions.deploy_function(func.id, ["node-1", "node-2"])
        assert result is True
        assert func.status == FunctionStatus.DEPLOYED
        assert len(func.deployed_nodes) == 2

    def test_undeploy_function(self):
        """Test undeploying a function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        functions.deploy_function(func.id, ["node-1"])
        result = functions.undeploy_function(func.id)
        assert result is True
        assert func.status == FunctionStatus.STOPPED

    def test_invoke_function(self):
        """Test invoking a function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        functions.deploy_function(func.id, ["node-1"])

        invocation = functions.invoke_function(func.id, {"key": "value"})
        assert invocation is not None
        assert invocation.function_id == func.id

    def test_invoke_undeployed_function(self):
        """Test invoking undeployed function"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")

        invocation = functions.invoke_function(func.id, {})
        assert invocation is None

    def test_complete_invocation(self):
        """Test completing an invocation"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        functions.deploy_function(func.id, ["node-1"])
        inv = functions.invoke_function(func.id, {})

        result = functions.complete_invocation(inv.id, {"result": "ok"}, 50.0)
        assert result is True
        assert inv.status == "completed"

    def test_fail_invocation(self):
        """Test failing an invocation"""
        functions = EdgeFunctions()
        func = functions.create_function("test", Runtime.PYTHON, "code")
        functions.deploy_function(func.id, ["node-1"])
        inv = functions.invoke_function(func.id, {})

        result = functions.fail_invocation(inv.id, "Runtime error")
        assert result is True
        assert inv.status == "failed"

    def test_get_function_by_name(self):
        """Test getting function by name"""
        functions = EdgeFunctions()
        functions.create_function("test-func", Runtime.PYTHON, "code")

        func = functions.get_function_by_name("test-func")
        assert func is not None

    def test_get_functions_by_runtime(self):
        """Test getting functions by runtime"""
        functions = EdgeFunctions()
        functions.create_function("py1", Runtime.PYTHON, "code")
        functions.create_function("js1", Runtime.NODEJS, "code")
        functions.create_function("py2", Runtime.PYTHON, "code")

        py_funcs = functions.get_functions_by_runtime(Runtime.PYTHON)
        assert len(py_funcs) == 2

    def test_get_metrics(self):
        """Test getting metrics"""
        functions = EdgeFunctions()
        functions.create_function("test", Runtime.PYTHON, "code")

        metrics = functions.get_metrics()
        assert metrics["total_functions"] == 1


# =============================================================================
# EDGE ORCHESTRATOR TESTS
# =============================================================================

class TestEdgeOrchestrator:
    """Tests for EdgeOrchestrator class"""

    def test_init(self):
        """Test orchestrator initialization"""
        orchestrator = EdgeOrchestrator()
        assert orchestrator is not None
        metrics = orchestrator.get_metrics()
        assert metrics["total_workflows"] == 0

    def test_create_workflow(self):
        """Test creating a workflow"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow(
            name="test-workflow",
            description="A test workflow"
        )
        assert workflow.name == "test-workflow"
        assert workflow.enabled is True

    def test_add_step(self):
        """Test adding a step"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")

        step = orchestrator.add_step(
            workflow_id=workflow.id,
            name="step-1",
            step_type=StepType.FUNCTION,
            function_id="func-1"
        )
        assert step is not None
        assert step.name == "step-1"
        assert len(workflow.steps) == 1

    def test_remove_step(self):
        """Test removing a step"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        step = orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)

        result = orchestrator.remove_step(workflow.id, step.id)
        assert result is True
        assert len(workflow.steps) == 0

    def test_start_execution(self):
        """Test starting an execution"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)

        execution = orchestrator.start_execution(workflow.id, {"input": "data"})
        assert execution is not None
        assert execution.status == OrchestrationStatus.RUNNING

    def test_complete_step(self):
        """Test completing a step"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        step = orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)
        execution = orchestrator.start_execution(workflow.id, {})

        result = orchestrator.complete_step(execution.id, step.id, {"result": "ok"})
        assert result is True
        assert execution.current_step == 1

    def test_fail_execution(self):
        """Test failing an execution"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)
        execution = orchestrator.start_execution(workflow.id, {})

        result = orchestrator.fail_execution(execution.id, "Step failed")
        assert result is True
        assert execution.status == OrchestrationStatus.FAILED

    def test_cancel_execution(self):
        """Test cancelling an execution"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)
        execution = orchestrator.start_execution(workflow.id, {})

        result = orchestrator.cancel_execution(execution.id)
        assert result is True
        assert execution.status == OrchestrationStatus.CANCELLED

    def test_enable_disable_workflow(self):
        """Test enabling and disabling workflow"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")

        orchestrator.disable_workflow(workflow.id)
        assert workflow.enabled is False

        orchestrator.enable_workflow(workflow.id)
        assert workflow.enabled is True

    def test_get_active_executions(self):
        """Test getting active executions"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")
        orchestrator.add_step(workflow.id, "step-1", StepType.FUNCTION)

        orchestrator.start_execution(workflow.id, {})
        orchestrator.start_execution(workflow.id, {})

        active = orchestrator.get_active_executions()
        assert len(active) == 2

    def test_delete_workflow(self):
        """Test deleting a workflow"""
        orchestrator = EdgeOrchestrator()
        workflow = orchestrator.create_workflow("test")

        result = orchestrator.delete_workflow(workflow.id)
        assert result is True
        assert orchestrator.get_workflow(workflow.id) is None

    def test_get_metrics(self):
        """Test getting metrics"""
        orchestrator = EdgeOrchestrator()
        orchestrator.create_workflow("test")

        metrics = orchestrator.get_metrics()
        assert metrics["total_workflows"] == 1
